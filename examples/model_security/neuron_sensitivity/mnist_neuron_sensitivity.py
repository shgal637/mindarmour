# Copyright 2023 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Test neuron sensitivity
"""

import time
import numpy as np
from scipy.special import softmax

from mindspore import Model
from mindspore import Tensor
from mindspore import context
from mindspore.train.serialization import load_checkpoint, load_param_into_net
from mindspore.nn import SoftmaxCrossEntropyWithLogits

from mindarmour.adv_robustness.attacks import FastGradientSignMethod
from mindarmour.adv_robustness.evaluations import NeuronMetric
from mindarmour.utils.logger import LogUtil

from examples.common.networks.lenet5.lenet5_net import LeNet5
from examples.common.dataset.data_processing import generate_mnist_dataset

LOGGER = LogUtil.get_instance()
LOGGER.set_level("INFO")
TAG = "NS_Test"


def test_neuron_sensitivity():
    """
    Neuron sensitivity test for CPU device.
    """
    # upload trained network
    ckpt_path = (
        "../../common/networks/lenet5/trained_ckpt_file/checkpoint_lenet-10_1875.ckpt"
    )
    net = LeNet5()
    load_dict = load_checkpoint(ckpt_path)
    load_param_into_net(net, load_dict)

    # get test data
    data_list = "../../common/dataset/MNIST/test"
    batch_size = 32
    ds = generate_mnist_dataset(data_list, batch_size)

    # prediction accuracy before attack
    model = Model(net)
    batch_num = 3  # the number of batches of attacking samples
    test_images = []
    test_labels = []
    predict_labels = []
    i = 0
    for data in ds.create_tuple_iterator(output_numpy=True):
        i += 1
        images = data[0].astype(np.float32)
        labels = data[1]
        test_images.append(images)
        test_labels.append(labels)
        pred_labels = np.argmax(model.predict(Tensor(images)).asnumpy(), axis=1)
        predict_labels.append(pred_labels)
        if i >= batch_num:
            break
    predict_labels = np.concatenate(predict_labels)
    true_labels = np.concatenate(test_labels)
    accuracy = np.mean(np.equal(predict_labels, true_labels))
    LOGGER.info(TAG, "prediction accuracy before attacking is : %s", accuracy)

    # attacking
    loss = SoftmaxCrossEntropyWithLogits(sparse=True)
    attack = FastGradientSignMethod(net, eps=0.3, loss_fn=loss)
    start_time = time.process_time()
    adv_data = attack.batch_generate(
        np.concatenate(test_images), true_labels, batch_size=32
    )
    stop_time = time.process_time()
    pred_logits_adv = model.predict(Tensor(adv_data)).asnumpy()
    # rescale predict confidences into (0, 1).
    pred_logits_adv = softmax(pred_logits_adv, axis=1)
    pred_labels_adv = np.argmax(pred_logits_adv, axis=1)
    accuracy_adv = np.mean(np.equal(pred_labels_adv, true_labels))
    LOGGER.info(TAG, "prediction accuracy after attacking is : %s", accuracy_adv)

    neuron_sensitivity = NeuronMetric(
        net,
        np.concatenate(test_images),
        adv_data,
        ["conv1", "conv2", "fc1", "fc2"],
    )
    nsense = neuron_sensitivity.neuron_sensitivity()
    print(nsense)
    LOGGER.info(
        TAG,
        "The average costing time is %s",
        (stop_time - start_time) / (batch_num * batch_size),
    )


if __name__ == "__main__":
    # device_target can be "CPU", "GPU" or "Ascend"
    context.set_context(mode=context.PYNATIVE_MODE, device_target="CPU")
    test_neuron_sensitivity()
