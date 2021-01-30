# Copyright 2021 Huawei Technologies Co., Ltd
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
# ============================================================================
"""
network config setting, will be used in sup_privacy.py
"""

from easydict import EasyDict as edict

mnist_cfg = edict({
    'num_classes': 10,  # the number of classes of model's output
    'epoch_size': 1,  # training epochs
    'batch_size': 32,  # batch size for training
    'image_height': 32,  # the height of training samples
    'image_width': 32,  # the width of training samples
    'save_checkpoint_steps': 1875,  # the interval steps for saving checkpoint file of the model
    'keep_checkpoint_max': 10,  # the maximum number of checkpoint files would be saved
    'device_target': 'Ascend',  # device used
    'data_path': './MNIST_unzip',  # the path of training and testing data set
    'dataset_sink_mode': False,  # whether deliver all training data to device one time
})
