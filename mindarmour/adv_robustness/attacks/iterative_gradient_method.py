# Copyright 2019 Huawei Technologies Co., Ltd
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
""" Iterative gradient method attack. """
from abc import abstractmethod

import numpy as np
from PIL import Image, ImageOps

from mindspore.nn import Cell

from mindarmour.utils.logger import LogUtil
from mindarmour.utils.util import WithLossCell, GradWrapWithLoss, to_tensor_tuple
from mindarmour.utils._check_param import check_inputs_labels, \
    normalize_value, check_model, check_value_positive, check_int_positive, \
    check_param_type, check_norm_level, check_param_multi_types
from .attack import Attack
from .gradient_method import FastGradientSignMethod

LOGGER = LogUtil.get_instance()
TAG = 'IterGrad'


def _reshape_l1_projection(values, eps=3):
    """
    `Implementation of L1 ball projection from:`_.

    .. _`Implementation of L1 ball projection from:`:
        https://stanford.edu/~jduchi/projects/DuchiShSiCh08.pdf

    Args:
        values (numpy.ndarray): Input data reshape into 2-dims.
        eps (float): L1 radius. Default: 3.

    Returns:
        numpy.ndarray, containing the projection.
    """
    abs_x = np.abs(values)
    abs_x = np.sum(abs_x, axis=1)
    indexes_b = (abs_x > eps)
    x_b = values[indexes_b]
    batch_size_b = x_b.shape[0]
    if batch_size_b == 0:
        return values

    # make the projection on l1 ball for elements outside the ball
    b_mu = -np.sort(-np.abs(x_b), axis=1)
    b_vv = np.arange(x_b.shape[1]).astype(np.float)
    b_st = (np.cumsum(b_mu, axis=1)-eps)/(b_vv+1)
    selected = (b_mu - b_st) > 0
    rho = np.sum((np.cumsum((1-selected), axis=1) == 0), axis=1)-1
    theta = np.take_along_axis(b_st, np.expand_dims(rho, axis=1), axis=1)
    proj_x_b = np.maximum(0, np.abs(x_b)-theta)*np.sign(x_b)

    # gather all the projected batch
    proj_x = np.copy(values)
    proj_x[indexes_b] = proj_x_b
    return proj_x


def _projection(values, eps, norm_level):
    """
    Implementation of values normalization within eps.

    Args:
        values (numpy.ndarray): Input data.
        eps (float): Project radius.
        norm_level (Union[int, char, numpy.inf]): Order of the norm. Possible
            values: np.inf, 1 or 2.

    Returns:
        numpy.ndarray, normalized values.

    Raises:
        NotImplementedError: If the norm_level is not in [1, 2, np.inf, '1',
            '2', 'inf'].
    """
    if norm_level in (1, '1'):
        sample_batch = values.shape[0]
        x_flat = values.reshape(sample_batch, -1)
        proj_flat = _reshape_l1_projection(x_flat, eps)
        return proj_flat.reshape(values.shape)
    if norm_level in (2, '2'):
        return eps*normalize_value(values, norm_level)
    if norm_level in (np.inf, 'inf'):
        return eps*np.sign(values)
    msg = 'Values of `norm_level` different from 1, 2 and `np.inf` are ' \
          'currently not supported.'
    LOGGER.error(TAG, msg)
    raise NotImplementedError(msg)


class IterativeGradientMethod(Attack):
    """
    Abstract base class for all iterative gradient based attacks.

    Args:
        network (Cell): Target model.
        eps (float): Proportion of adversarial perturbation generated by the
            attack to data range. Default: 0.3.
        eps_iter (float): Proportion of single-step adversarial perturbation
            generated by the attack to data range. Default: 0.1.
        bounds (tuple): Upper and lower bounds of data, indicating the data range.
            In form of (clip_min, clip_max). Default: (0.0, 1.0).
        nb_iter (int): Number of iteration. Default: 5.
        loss_fn (Loss): Loss function for optimization. If None, the input network \
            is already equipped with loss function. Default: None.
    """
    def __init__(self, network, eps=0.3, eps_iter=0.1, bounds=(0.0, 1.0), nb_iter=5,
                 loss_fn=None):
        super(IterativeGradientMethod, self).__init__()
        self._network = check_model('network', network, Cell)
        self._eps = check_value_positive('eps', eps)
        self._eps_iter = check_value_positive('eps_iter', eps_iter)
        self._nb_iter = check_int_positive('nb_iter', nb_iter)
        self._bounds = None
        if bounds is not None:
            self._bounds = check_param_multi_types('bounds', bounds, [list, tuple])
            for b in self._bounds:
                _ = check_param_multi_types('bound', b, [int, float])
        if loss_fn is None:
            self._loss_grad = network
        else:
            self._loss_grad = GradWrapWithLoss(WithLossCell(self._network, loss_fn))
        self._loss_grad.set_train()

    @abstractmethod
    def generate(self, inputs, labels):
        """
        Generate adversarial examples based on input samples and original/target labels.

        Args:
            inputs (Union[numpy.ndarray, tuple]): Benign input samples used as references to create
                adversarial examples.
            labels (Union[numpy.ndarray, tuple]): Original/target labels. \
                For each input if it has more than one label, it is wrapped in a tuple.
        Raises:
            NotImplementedError: This function is not available in
                IterativeGradientMethod.
        """
        msg = 'The function generate() is an abstract method in class ' \
              '`IterativeGradientMethod`, and should be implemented ' \
              'in child class.'
        LOGGER.error(TAG, msg)
        raise NotImplementedError(msg)


class BasicIterativeMethod(IterativeGradientMethod):
    """
    The Basic Iterative Method attack, an iterative FGSM method to generate
    adversarial examples.

    References: `A. Kurakin, I. Goodfellow, and S. Bengio, "Adversarial examples
    in the physical world," in ICLR, 2017 <https://arxiv.org/abs/1607.02533>`_

    Args:
        network (Cell): Target model.
        eps (float): Proportion of adversarial perturbation generated by the
            attack to data range. Default: 0.3.
        eps_iter (float): Proportion of single-step adversarial perturbation
            generated by the attack to data range. Default: 0.1.
        bounds (tuple): Upper and lower bounds of data, indicating the data range.
            In form of (clip_min, clip_max). Default: (0.0, 1.0).
        is_targeted (bool): If True, targeted attack. If False, untargeted
            attack. Default: False.
        nb_iter (int): Number of iteration. Default: 5.
        loss_fn (Loss): Loss function for optimization. If None, the input network \
            is already equipped with loss function. Default: None.

    Examples:
        >>> from mindspore.ops import operations as P
        >>> from mindspore.nn import Cell, SoftmaxCrossEntropyWithLogits
        >>> from mindarmour.adv_robustness.attacks import BasicIterativeMethod
        >>> class Net(Cell):
        ...     def __init__(self):
        ...         super(Net, self).__init__()
        ...         self._softmax = P.Softmax()
        ...     def construct(self, inputs):
        ...         out = self._softmax(inputs)
        ...         return out
        >>> net = Net()
        >>> attack = BasicIterativeMethod(net, loss_fn=SoftmaxCrossEntropyWithLogits(sparse=False))
        >>> inputs = np.asarray([[0.1, 0.2, 0.7]], np.float32)
        >>> labels = np.asarray([2],np.int32)
        >>> labels = np.eye(3)[labels].astype(np.float32)
        >>> net = Net()
        >>> adv_x = attack.generate(inputs, labels)
    """
    def __init__(self, network, eps=0.3, eps_iter=0.1, bounds=(0.0, 1.0),
                 is_targeted=False, nb_iter=5, loss_fn=None):
        super(BasicIterativeMethod, self).__init__(network,
                                                   eps=eps,
                                                   eps_iter=eps_iter,
                                                   bounds=bounds,
                                                   nb_iter=nb_iter,
                                                   loss_fn=loss_fn)
        self._is_targeted = check_param_type('is_targeted', is_targeted, bool)
        self._attack = FastGradientSignMethod(self._network,
                                              eps=self._eps_iter,
                                              bounds=self._bounds,
                                              is_targeted=self._is_targeted,
                                              loss_fn=loss_fn)

    def generate(self, inputs, labels):

        """
        Simple iterative FGSM method to generate adversarial examples.

        Args:
            inputs (Union[numpy.ndarray, tuple]): Benign input samples used as references to
                create adversarial examples.
            labels (Union[numpy.ndarray, tuple]): Original/target labels. \
                For each input if it has more than one label, it is wrapped in a tuple.
        Returns:
            numpy.ndarray, generated adversarial examples.
        """
        inputs_image, inputs, labels = check_inputs_labels(inputs, labels)
        arr_x = inputs_image
        if self._bounds is not None:
            clip_min, clip_max = self._bounds
            clip_diff = clip_max - clip_min
            for _ in range(self._nb_iter):
                if 'self._prob' in globals():
                    d_inputs = _transform_inputs(inputs_image, self._prob)
                else:
                    d_inputs = inputs_image
                if isinstance(inputs, tuple):
                    d_inputs = (d_inputs,) + inputs[1:]
                adv_x = self._attack.generate(d_inputs, labels)
                perturs = np.clip(adv_x - arr_x, (0 - self._eps)*clip_diff,
                                  self._eps*clip_diff)
                adv_x = arr_x + perturs
                inputs_image = adv_x
        else:
            for _ in range(self._nb_iter):
                if 'self._prob' in globals():
                    d_inputs = _transform_inputs(inputs_image, self._prob)
                else:
                    d_inputs = inputs_image
                if isinstance(inputs, tuple):
                    d_inputs = (inputs_image,) + inputs[1:]
                adv_x = self._attack.generate(d_inputs, labels)
                adv_x = np.clip(adv_x, arr_x - self._eps, arr_x + self._eps)
                inputs_image = adv_x
        return adv_x


class MomentumIterativeMethod(IterativeGradientMethod):
    """
    The Momentum Iterative Method attack accelerates the gradient descent algorithm,
    such as FGSM, FGM, and LLCM, by accumulating a velocity vector in the gradient
    direction of the loss function across iterations, and thus generates the adversarial examples.


    References: `Y. Dong, et al., "Boosting adversarial attacks with
    momentum," arXiv:1710.06081, 2017 <https://arxiv.org/abs/1710.06081>`_

    Args:
        network (Cell): Target model.
        eps (float): Proportion of adversarial perturbation generated by the
            attack to data range. Default: 0.3.
        eps_iter (float): Proportion of single-step adversarial perturbation
            generated by the attack to data range. Default: 0.1.
        bounds (tuple): Upper and lower bounds of data, indicating the data range.
            In form of (clip_min, clip_max). Default: (0.0, 1.0).
        is_targeted (bool): If True, targeted attack. If False, untargeted
            attack. Default: False.
        nb_iter (int): Number of iteration. Default: 5.
        decay_factor (float): Decay factor in iterations. Default: 1.0.
        norm_level (Union[int, numpy.inf]): Order of the norm. Possible values:
            np.inf, 1 or 2. Default: 'inf'.
        loss_fn (Loss): Loss function for optimization. If None, the input network \
            is already equipped with loss function. Default: None.

    Examples:
        >>> from mindspore.ops import operations as P
        >>> from mindspore.nn import Cell, SoftmaxCrossEntropyWithLogits
        >>> from mindarmour.adv_robustness.attacks import MomentumIterativeMethod
        >>> class Net(Cell):
        ...     def __init__(self):
        ...         super(Net, self).__init__()
        ...         self._softmax = P.Softmax()
        ...     def construct(self, inputs):
        ...         out = self._softmax(inputs)
        ...         return out
        >>> net = Net()
        >>> attack = MomentumIterativeMethod(net, loss_fn=SoftmaxCrossEntropyWithLogits(sparse=False))
        >>> inputs = np.asarray([[0.1, 0.2, 0.7]], np.float32)
        >>> labels = np.asarray([2],np.int32)
        >>> labels = np.eye(3)[labels].astype(np.float32)
        >>> net = Net()
        >>> adv_x = attack.generate(inputs, labels)
    """

    def __init__(self, network, eps=0.3, eps_iter=0.1, bounds=(0.0, 1.0),
                 is_targeted=False, nb_iter=5, decay_factor=1.0,
                 norm_level='inf', loss_fn=None):
        super(MomentumIterativeMethod, self).__init__(network,
                                                      eps=eps,
                                                      eps_iter=eps_iter,
                                                      bounds=bounds,
                                                      nb_iter=nb_iter,
                                                      loss_fn=loss_fn)
        self._is_targeted = check_param_type('is_targeted', is_targeted, bool)
        self._decay_factor = check_value_positive('decay_factor', decay_factor)
        self._norm_level = check_norm_level(norm_level)

    def generate(self, inputs, labels):
        """
        Generate adversarial examples based on input data and origin/target labels.

        Args:
            inputs (Union[numpy.ndarray, tuple]): Benign input samples used as references to
                create adversarial examples.
            labels (Union[numpy.ndarray, tuple]): Original/target labels. \
                For each input if it has more than one label, it is wrapped in a tuple.

        Returns:
            numpy.ndarray, generated adversarial examples.
        """
        inputs_image, inputs, labels = check_inputs_labels(inputs, labels)
        arr_x = inputs_image
        momentum = 0
        if self._bounds is not None:
            clip_min, clip_max = self._bounds
            clip_diff = clip_max - clip_min
            for _ in range(self._nb_iter):
                if 'self._prob' in globals():
                    d_inputs = _transform_inputs(inputs_image, self._prob)
                else:
                    d_inputs = inputs_image
                if isinstance(inputs, tuple):
                    d_inputs = (d_inputs,) + inputs[1:]
                gradient = self._gradient(d_inputs, labels)
                momentum = self._decay_factor*momentum + gradient
                if isinstance(d_inputs, tuple):
                    adv_x = d_inputs[0] + self._eps_iter*np.sign(momentum)
                else:
                    adv_x = d_inputs + self._eps_iter*np.sign(momentum)
                perturs = np.clip(adv_x - arr_x, (0 - self._eps)*clip_diff,
                                  self._eps*clip_diff)
                adv_x = arr_x + perturs
                adv_x = np.clip(adv_x, clip_min, clip_max)
                inputs_image = adv_x
        else:
            for _ in range(self._nb_iter):
                if 'self._prob' in globals():
                    d_inputs = _transform_inputs(inputs_image, self._prob)
                else:
                    d_inputs = inputs_image
                if isinstance(inputs, tuple):
                    d_inputs = (d_inputs,) + inputs[1:]
                gradient = self._gradient(d_inputs, labels)
                momentum = self._decay_factor*momentum + gradient
                if isinstance(d_inputs, tuple):
                    adv_x = d_inputs[0] + self._eps_iter*np.sign(momentum)
                else:
                    adv_x = d_inputs + self._eps_iter*np.sign(momentum)
                adv_x = np.clip(adv_x, arr_x - self._eps, arr_x + self._eps)
                inputs_image = adv_x
        return adv_x

    def _gradient(self, inputs, labels):
        """
        Calculate the gradient of input samples.

        Args:
            inputs (Union[numpy.ndarray, tuple]): Input samples.
            labels (Union[numpy.ndarray, tuple]): Original/target labels. \
                For each input if it has more than one label, it is wrapped in a tuple.

        Returns:
            numpy.ndarray, gradient of labels w.r.t inputs.

        Examples:
            >>> grad = self._gradient([[0.5, 0.3, 0.4]],
            ...                       [[0, 0, 0, 1, 0, 0, 0, 0, 0, 0])
        """
        # get grad of loss over x
        inputs_tensor = to_tensor_tuple(inputs)
        labels_tensor = to_tensor_tuple(labels)
        out_grad = self._loss_grad(*inputs_tensor, *labels_tensor)
        if isinstance(out_grad, tuple):
            out_grad = out_grad[0]
        gradient = out_grad.asnumpy()

        if self._is_targeted:
            gradient = -gradient
        return normalize_value(gradient, self._norm_level)


class ProjectedGradientDescent(BasicIterativeMethod):
    """
    The Projected Gradient Descent attack is a variant of the Basic Iterative
    Method in which, after each iteration, the perturbation is projected on an
    lp-ball of specified radius (in addition to clipping the values of the
    adversarial sample so that it lies in the permitted data range). This is
    the attack proposed by Madry et al. for adversarial training.

    References: `A. Madry, et al., "Towards deep learning models resistant to
    adversarial attacks," in ICLR, 2018 <https://arxiv.org/abs/1706.06083>`_

    Args:
        network (Cell): Target model.
        eps (float): Proportion of adversarial perturbation generated by the
            attack to data range. Default: 0.3.
        eps_iter (float): Proportion of single-step adversarial perturbation
            generated by the attack to data range. Default: 0.1.
        bounds (tuple): Upper and lower bounds of data, indicating the data range.
            In form of (clip_min, clip_max). Default: (0.0, 1.0).
        is_targeted (bool): If True, targeted attack. If False, untargeted
            attack. Default: False.
        nb_iter (int): Number of iteration. Default: 5.
        norm_level (Union[int, numpy.inf]): Order of the norm. Possible values:
            np.inf, 1 or 2. Default: 'inf'.
        loss_fn (Loss): Loss function for optimization. If None, the input network \
            is already equipped with loss function. Default: None.

    Examples:
        >>> from mindspore.ops import operations as P
        >>> from mindspore.nn import Cell, SoftmaxCrossEntropyWithLogits
        >>> from mindarmour.adv_robustness.attacks import ProjectedGradientDescent
        >>> class Net(Cell):
        ...     def __init__(self):
        ...         super(Net, self).__init__()
        ...         self._softmax = P.Softmax()
        ...     def construct(self, inputs):
        ...         out = self._softmax(inputs)
        ...         return out
        >>> net = Net()
        >>> attack = ProjectedGradientDescent(net, loss_fn=SoftmaxCrossEntropyWithLogits(sparse=False))
        >>> inputs = np.asarray([[0.1, 0.2, 0.7]], np.float32)
        >>> labels = np.asarray([2],np.int32)
        >>> labels = np.eye(3)[labels].astype(np.float32)
        >>> net = Net()
        >>> adv_x = attack.generate(inputs, labels)
    """

    def __init__(self, network, eps=0.3, eps_iter=0.1, bounds=(0.0, 1.0),
                 is_targeted=False, nb_iter=5, norm_level='inf', loss_fn=None):
        super(ProjectedGradientDescent, self).__init__(network,
                                                       eps=eps,
                                                       eps_iter=eps_iter,
                                                       bounds=bounds,
                                                       is_targeted=is_targeted,
                                                       nb_iter=nb_iter,
                                                       loss_fn=loss_fn)
        self._norm_level = check_norm_level(norm_level)

    def generate(self, inputs, labels):
        """
        Iteratively generate adversarial examples based on BIM method. The
        perturbation is normalized by projected method with parameter norm_level .

        Args:
            inputs (Union[numpy.ndarray, tuple]): Benign input samples used as references to
                create adversarial examples.
            labels (Union[numpy.ndarray, tuple]): Original/target labels. \
                For each input if it has more than one label, it is wrapped in a tuple.

        Returns:
            numpy.ndarray, generated adversarial examples.
        """
        inputs_image, inputs, labels = check_inputs_labels(inputs, labels)
        arr_x = inputs_image
        if self._bounds is not None:
            clip_min, clip_max = self._bounds
            clip_diff = clip_max - clip_min
            for _ in range(self._nb_iter):
                adv_x = self._attack.generate(inputs, labels)
                perturs = _projection(adv_x - arr_x,
                                      self._eps,
                                      norm_level=self._norm_level)
                perturs = np.clip(perturs, (0 - self._eps)*clip_diff,
                                  self._eps*clip_diff)
                adv_x = arr_x + perturs
                if isinstance(inputs, tuple):
                    inputs = (adv_x,) + inputs[1:]
                else:
                    inputs = adv_x
        else:
            for _ in range(self._nb_iter):
                adv_x = self._attack.generate(inputs, labels)
                perturs = _projection(adv_x - arr_x,
                                      self._eps,
                                      norm_level=self._norm_level)
                adv_x = arr_x + perturs
                adv_x = np.clip(adv_x, arr_x - self._eps, arr_x + self._eps)
                if isinstance(inputs, tuple):
                    inputs = (adv_x,) + inputs[1:]
                else:
                    inputs = adv_x
        return adv_x


class DiverseInputIterativeMethod(BasicIterativeMethod):
    """
    The Diverse Input Iterative Method attack follows the basic iterative method,
    and applies random transformation to the input data at each iteration. Such transformation
    on the input data could improve the transferability of the adversarial examples.

    References: `Xie, Cihang and Zhang, et al., "Improving Transferability of
    Adversarial Examples With Input Diversity," in CVPR, 2019 <https://arxiv.org/abs/1803.06978>`_

    Args:
        network (Cell): Target model.
        eps (float): Proportion of adversarial perturbation generated by the
            attack to data range. Default: 0.3.
        bounds (tuple): Upper and lower bounds of data, indicating the data range.
            In form of (clip_min, clip_max). Default: (0.0, 1.0).
        is_targeted (bool): If True, targeted attack. If False, untargeted
            attack. Default: False.
        prob (float): Transformation probability. Default: 0.5.
        loss_fn (Loss): Loss function for optimization. If None, the input network \
            is already equipped with loss function. Default: None.

    Examples:
        >>> from mindspore.ops import operations as P
        >>> from mindspore.nn import Cell, SoftmaxCrossEntropyWithLogits
        >>> from mindarmour.adv_robustness.attacks import DiverseInputIterativeMethod
        >>> class Net(Cell):
        ...     def __init__(self):
        ...         super(Net, self).__init__()
        ...         self._softmax = P.Softmax()
        ...     def construct(self, inputs):
        ...         out = self._softmax(inputs)
        ...         return out
        >>> net = Net()
        >>> attack = DiverseInputIterativeMethod(net, loss_fn=SoftmaxCrossEntropyWithLogits(sparse=False))
        >>> inputs = np.asarray([[0.1, 0.2, 0.7]], np.float32)
        >>> labels = np.asarray([2],np.int32)
        >>> labels = np.eye(3)[labels].astype(np.float32)
        >>> net = Net()
        >>> adv_x = attack.generate(inputs, labels)
    """
    def __init__(self, network, eps=0.3, bounds=(0.0, 1.0),
                 is_targeted=False, prob=0.5, loss_fn=None):
        # reference to paper hyper parameters setting.
        eps_iter = 16*2/255
        nb_iter = int(min(eps*255 + 4, 1.25*255*eps))
        super(DiverseInputIterativeMethod, self).__init__(network,
                                                          eps=eps,
                                                          eps_iter=eps_iter,
                                                          bounds=bounds,
                                                          is_targeted=is_targeted,
                                                          nb_iter=nb_iter,
                                                          loss_fn=loss_fn)
        self._prob = check_param_type('prob', prob, float)


class MomentumDiverseInputIterativeMethod(MomentumIterativeMethod):
    """
    The Momentum Diverse Input Iterative Method attack is a momentum iterative method,
    and applies random transformation to the input data at each iteration. Such transformation
    on the input data could improve the transferability of the adversarial examples.


    References: `Xie, Cihang and Zhang, et al., "Improving Transferability of
    Adversarial Examples With Input Diversity," in CVPR, 2019 <https://arxiv.org/abs/1803.06978>`_

    Args:
        network (Cell): Target model.
        eps (float): Proportion of adversarial perturbation generated by the
            attack to data range. Default: 0.3.
        bounds (tuple): Upper and lower bounds of data, indicating the data range.
            In form of (clip_min, clip_max). Default: (0.0, 1.0).
        is_targeted (bool): If True, targeted attack. If False, untargeted
            attack. Default: False.
        norm_level (Union[int, numpy.inf]): Order of the norm. Possible values:
            np.inf, 1 or 2. Default: 'l1'.
        prob (float): Transformation probability. Default: 0.5.
        loss_fn (Loss): Loss function for optimization. If None, the input network \
            is already equipped with loss function. Default: None.

    Examples:
        >>> from mindspore.ops import operations as P
        >>> from mindspore.nn import Cell, SoftmaxCrossEntropyWithLogits
        >>> from mindarmour.adv_robustness.attacks import MomentumDiverseInputIterativeMethod
        >>> class Net(Cell):
        ...     def __init__(self):
        ...         super(Net, self).__init__()
        ...         self._softmax = P.Softmax()
        ...     def construct(self, inputs):
        ...         out = self._softmax(inputs)
        ...         return out
        >>> net = Net()
        >>> attack = MomentumDiverseInputIterativeMethod(net, loss_fn=SoftmaxCrossEntropyWithLogits(sparse=False))
        >>> inputs = np.asarray([[0.1, 0.2, 0.7]], np.float32)
        >>> labels = np.asarray([2],np.int32)
        >>> labels = np.eye(3)[labels].astype(np.float32)
        >>> net = Net()
        >>> adv_x = attack.generate(inputs, labels)
       """
    def __init__(self, network, eps=0.3, bounds=(0.0, 1.0),
                 is_targeted=False, norm_level='l1', prob=0.5, loss_fn=None):
        eps_iter = 16*2 / 255
        nb_iter = int(min(eps*255 + 4, 1.25*255*eps))
        super(MomentumDiverseInputIterativeMethod, self).__init__(network=network,
                                                                  eps=eps,
                                                                  eps_iter=eps_iter,
                                                                  bounds=bounds,
                                                                  nb_iter=nb_iter,
                                                                  is_targeted=is_targeted,
                                                                  norm_level=norm_level,
                                                                  loss_fn=loss_fn)
        self._prob = check_param_type('prob', prob, float)


def _transform_inputs(inputs, prob, low=29, high=33, full_aug=False):
    """
    Inputs data augmentation.

    Args:
        inputs (Union[np.int8, np.float]): Inputs.
        prob (float): The probability of augmentation.
        low (int): Lower bound of resize image width. Default: 29.
        high (int): Upper bound of resize image height. Default: 33.
        full_aug (bool): type of augmentation method, use interpolation and padding
            as default. Default: False.

    Returns:
        numpy.ndarray, the augmentation data.
    """
    raw_shape = inputs[0].shape
    tran_mask = np.random.uniform(0, 1, size=inputs.shape[0]) < prob
    tran_inputs = inputs[tran_mask]
    raw_inputs = inputs[tran_mask == 0]
    tran_outputs = []
    for sample in tran_inputs:
        width = np.random.choice(np.arange(low, high))
        # resize
        sample = (sample*255).astype(np.uint8)
        d_image = Image.fromarray(sample, mode='L').resize((width, width), Image.NEAREST)
        # pad
        left_pad = (raw_shape[0] - width) // 2
        right_pad = raw_shape[0] - width - left_pad
        top_pad = (raw_shape[1] - width) // 2
        bottom_pad = raw_shape[1] - width - top_pad
        p_sample = ImageOps.expand(d_image,
                                   border=(left_pad, top_pad, right_pad, bottom_pad))
        tran_outputs.append(np.array(p_sample).astype(np.float) / 255)
    if full_aug:
        # gaussian noise
        tran_outputs = np.random.normal(np.array(tran_outputs).shape) + tran_outputs
    tran_outputs.extend(raw_inputs)
    if not np.any(tran_outputs-raw_inputs):
        LOGGER.error(TAG, 'the transform function does not take effect.')
    return tran_outputs
