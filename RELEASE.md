# MindSpore Armour Release Notes

[查看中文](./RELEASE_CN.md)

## MindSpore Armour 2.0.0 Release Notes

### Major Features and Improvements

* Add version check with MindSpore.
* Upgrade the related software packages, Pillow>=9.3.0，scipy>=1.5.2，pytest>=5.4.3.

### Contributors

Thanks goes to these wonderful people:

Zhang Shukun, Liu Zhidan, Jin Xiulang, Liu Liu, Tang Cong, Yang Yuan, Li Hongcheng.

Contributions of any kind are welcome!

## MindArmour 1.9.0 Release Notes

### API Change

* Add Chinese version api of natural robustness feature.

### Contributors

Thanks goes to these wonderful people:

Liu Zhidan, Zhang Shukun, Jin Xiulang, Liu Liu, Tang Cong, Yangyuan.

Contributions of any kind are welcome!

## MindArmour 1.8.0 Release Notes

### API Change

* Add Chinese version of all existed api.

### Contributors

Thanks goes to these wonderful people:

Zhang Shukun, Liu Zhidan, Jin Xiulang, Liu Liu, Tang Cong, Yangyuan.

Contributions of any kind are welcome!

## MindArmour 1.7.0 Release Notes

### Major Features and Improvements

#### Robustness

* [STABLE] Real-World Robustness Evaluation Methods

### API Change

* Change value of parameter `mutate_config` in  `mindarmour.fuzz_testing.Fuzzer.fuzzing` interface. ([!333](https://gitee.com/mindspore/mindarmour/pulls/333))

### Bug fixes

* Update version of third-party dependence pillow from more than or equal to 6.2.0 to more than or equal to 7.2.0. ([!329](https://gitee.com/mindspore/mindarmour/pulls/329))

### Contributors

Thanks goes to these wonderful people:

Liu Zhidan, Zhang Shukun, Jin Xiulang, Liu Liu.

Contributions of any kind are welcome!

# MindArmour 1.６.0

## MindArmour 1.６.0 Release Notes

### Major Features and Improvements

#### Reliability

* [BETA] Data Drift Detection for Image Data
* [BETA] Model Fault Injection

### Bug fixes

### Contributors

Thanks goes to these wonderful people:

Wu Xiaoyu，Feng Zhenye, Liu Zhidan, Jin Xiulang, Liu Luobin, Liu Liu, Zhang Shukun

# MindArmour 1.5.0

## MindArmour 1.5.0 Release Notes

### Major Features and Improvements

#### Reliability

* [BETA] Reconstruct AI Fuzz and Neuron Coverage Metrics

### Bug fixes

### Contributors

Thanks goes to these wonderful people:

Wu Xiaoyu，Liu Zhidan, Jin Xiulang, Liu Luobin, Liu Liu

# MindArmour 1.3.0-rc1

## MindArmour 1.3.0 Release Notes

### Major Features and Improvements

#### Privacy

* [STABLE] Data Drift Detection for Time Series Data

### Bug fixes

* [BUGFIX] Optimization of API description.

### Contributors

Thanks goes to these wonderful people:

Wu Xiaoyu，Liu Zhidan, Jin Xiulang, Liu Luobin, Liu Liu

# MindArmour 1.2.0

## MindArmour 1.2.0 Release Notes

### Major Features and Improvements

#### Privacy

* [STABLE] Tailored-based privacy protection technology (Pynative)
* [STABLE] Model Inversion. Reverse analysis technology of privacy information

### API Change

#### Backwards Incompatible Change

##### C++ API

[Modify] ...
[Add] ...
[Delete] ...

##### Java API

[Add] ...

#### Deprecations

##### C++ API

##### Java API

### Bug fixes

[BUGFIX] ...

### Contributors

Thanks goes to these wonderful people:

han.yin

# MindArmour 1.1.0 Release Notes

## MindArmour

### Major Features and Improvements

* [STABLE] Attack capability of the Object Detection models.
    * Some white-box adversarial attacks, such as [iterative] gradient method and DeepFool now can be applied to Object Detection models.
    * Some black-box adversarial attacks, such as PSO and Genetic Attack now can be applied to Object Detection models.

### Backwards Incompatible Change

#### Python API

#### C++ API

### Deprecations

#### Python API

#### C++ API

### New Features

#### Python API

#### C++ API

### Improvements

#### Python API

#### C++ API

### Bug fixes

#### Python API

#### C++ API

## Contributors

Thanks goes to these wonderful people:

Xiulang Jin, Zhidan Liu, Luobin Liu and Liu Liu.

Contributions of any kind are welcome!

# Release 1.0.0

## Major Features and Improvements

### Differential privacy model training

* Privacy leakage evaluation.

    * Parameter verification enhancement.
    * Support parallel computing.

### Model robustness evaluation

* Fuzzing based Adversarial Robustness testing.

    * Parameter verification enhancement.

### Other

* Api & Directory Structure
    * Adjusted the directory structure based on different features.
    * Optimize the structure of examples.

## Bugfixes

## Contributors

Thanks goes to these wonderful people:

Liu Liu, Xiulang Jin, Zhidan Liu and Luobin Liu.

Contributions of any kind are welcome!

# Release 0.7.0-beta

## Major Features and Improvements

### Differential privacy model training

* Privacy leakage evaluation.

    * Using Membership inference to evaluate the effectiveness of privacy-preserving techniques for AI.

### Model robustness evaluation

* Fuzzing based Adversarial Robustness testing.

    * Coverage-guided test set generation.

## Bugfixes

## Contributors

Thanks goes to these wonderful people:

Liu Liu, Xiulang Jin, Zhidan Liu, Luobin Liu and Huanhuan Zheng.

Contributions of any kind are welcome!

# Release 0.6.0-beta

## Major Features and Improvements

### Differential privacy model training

* Optimizers with differential privacy

    * Differential privacy model training now supports some new policies.

    * Adaptive Norm policy is supported.

    * Adaptive Noise policy with exponential decrease is supported.  

* Differential Privacy Training Monitor

    * A new monitor is supported using zCDP as its asymptotic budget estimator.

## Bugfixes

## Contributors

Thanks goes to these wonderful people:

Liu Liu, Huanhuan Zheng, XiuLang jin, Zhidan liu.

Contributions of any kind are welcome.

# Release 0.5.0-beta

## Major Features and Improvements

### Differential privacy model training

* Optimizers with differential privacy

    * Differential privacy model training now supports both Pynative mode and graph mode.

    * Graph mode is recommended for its performance.

## Bugfixes

## Contributors

Thanks goes to these wonderful people:

Liu Liu, Huanhuan Zheng, Xiulang Jin, Zhidan Liu.

Contributions of any kind are welcome!

# Release 0.3.0-alpha

## Major Features and Improvements

### Differential Privacy Model Training

Differential Privacy is coming! By using Differential-Privacy-Optimizers, one can still train a model as usual, while the trained model preserved the privacy of training dataset, satisfying the definition of
differential privacy with proper budget.

* Optimizers with Differential Privacy([PR23](https://gitee.com/mindspore/mindarmour/pulls/23), [PR24](https://gitee.com/mindspore/mindarmour/pulls/24))

    * Some common optimizers now have a differential privacy version (SGD/Adam). We are adding more.
    * Automatically and adaptively add Gaussian Noise during training to achieve Differential Privacy.
    * Automatically stop training when Differential Privacy Budget exceeds.

* Differential Privacy Monitor([PR22](https://gitee.com/mindspore/mindarmour/pulls/22))

    * Calculate overall budget consumed during training, indicating the ultimate protect effect.

## Bug fixes

## Contributors

Thanks goes to these wonderful people:
Liu Liu, Huanhuan Zheng, Zhidan Liu, Xiulang Jin
Contributions of any kind are welcome!

# Release 0.2.0-alpha

## Major Features and Improvements

* Add a white-box attack method: M-DI2-FGSM([PR14](https://gitee.com/mindspore/mindarmour/pulls/14)).
* Add three neuron coverage metrics: KMNCov, NBCov, SNACov([PR12](https://gitee.com/mindspore/mindarmour/pulls/12)).
* Add a coverage-guided fuzzing test framework for deep neural networks([PR13](https://gitee.com/mindspore/mindarmour/pulls/13)).
* Update the MNIST Lenet5 examples.
* Remove some duplicate code.

## Bug fixes

## Contributors

Thanks goes to these wonderful people:
Liu Liu, Huanhuan Zheng, Zhidan Liu, Xiulang Jin
Contributions of any kind are welcome!

# Release 0.1.0-alpha

Initial release of MindArmour.

## Major Features

* Support adversarial attack and defense on the platform of MindSpore.
* Include 13 white-box and 7 black-box attack methods.
* Provide 5 detection algorithms to detect attacking in multiple way.
* Provide adversarial training to enhance model security.
* Provide 6 evaluation metrics for attack methods and 9 evaluation metrics for defense methods.
