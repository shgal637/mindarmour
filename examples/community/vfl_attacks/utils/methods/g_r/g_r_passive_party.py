# Copyright 2024 Huawei Technologies Co., Ltd
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
This module defines the passive party for gradient-replacement attack.
"""
import random
from mindspore import ops
from party.passive_party import VFLPassiveModel

class GRPassiveModel(VFLPassiveModel):
    """
    Malicious passive party for gradient-replacement backdoor.
    """
    def __init__(self, bottom_model, amplify_ratio=1, id=None, args=None):
        super(GRPassiveModel, self).__init__(bottom_model, id=id, args=args)
        self.backdoor_indices = None
        self.target_grad = None
        self.target_indices = None
        self.amplify_ratio = amplify_ratio
        self.components = None
        self.is_debug = False
        self.pair_set = {}
        self.target_gradients = {}
        self.backdoor_X = {}

    def set_epoch(self, epoch):
        """
        Set the current epoch for the passive party.
        Args:
            epoch (int): The current epoch for the passive party.
        """
        self.epoch = epoch

    def set_backdoor_indices(self, target_indices, backdoor_indices, backdoor_X):
        """
        Set the target indices, backdoor indices and backdoor samples.

        Args:
            target_indices (List[int]): Indices of samples labeled as the backdoor class in the normal train dataset.
            backdoor_indices (List[int]): Indices of backdoor samples in the normal train dataset,
                                    used for gradient replacement.
            backdoor_X (Tensor): The poisoned samples.
        """
        self.target_indices = target_indices
        self.backdoor_indices = backdoor_indices
        self.backdoor_X = backdoor_X

    def receive_gradients(self, gradients):
        """
        Receive gradients from the active party and update parameters of the local bottom model.

        Args:
            gradients (List[Tensor]): Gradients from the active party.
        """
        gradients = gradients.copy()
        # Get the target gradient of samples labeled backdoor class.
        for index, i in enumerate(self.indices):
            i = i.item()
            if i in self.target_indices:
                self.target_gradients[i] = gradients[index]

        # Replace the gradient of backdoor samples with the target gradient.
        for index, j in enumerate(self.indices):
            j = j.item()
            if j in self.backdoor_indices:
                for i, v in self.pair_set.items():
                    if v == j:
                        target_grad = self.target_gradients[i]
                        if target_grad is not None:
                            gradients[index] = self.amplify_ratio * target_grad
                        break

        self.common_grad = gradients
        self._fit(self.X, self.components)

    def send_components(self):
        """
        Send latent representation to the active party.
        """
        result = self._forward_computation(self.X)
        self.components = result
        send_result = result.copy()
        for index, i in enumerate(self.indices):
            i = i.item()
            if i in self.target_indices:
                if i not in self.pair_set.keys():
                    j = self.backdoor_indices[random.randint(0, len(self.backdoor_indices)-1)]
                    self.pair_set[i] = j
                else:
                    j = self.pair_set[i]
                send_result[index] = self.bottom_model.forward(ops.unsqueeze(self.backdoor_X[j], 0))[0]

        return send_result
