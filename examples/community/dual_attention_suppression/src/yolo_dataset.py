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
# ============================================================================
"""YOLO dataset."""
import os
import random

import cv2
import mindspore.dataset as de
import mindspore.dataset.vision as CV
import numpy as np
from PIL import Image
from pycocotools.coco import COCO

from src.distributed_sampler import DistributedSampler
from src.transforms import MultiScaleTrans
from src.transforms import PreprocessTrueBox
from src.transforms import reshape_fn

min_keypoints_per_image = 10


def _has_only_empty_bbox(anno):
    """has only empty bbox"""
    return all(any(o <= 1 for o in obj["bbox"][2:]) for obj in anno)


def _count_visible_keypoints(anno):
    """count visible keypoints"""
    return sum(sum(1 for v in ann["keypoints"][2::3] if v > 0) for ann in anno)


def has_valid_annotation(anno):
    """Check annotation file."""
    # if it's empty, there is no annotation
    if not anno:
        return False
    # if all boxes have close to zero area, there is no annotation
    if _has_only_empty_bbox(anno):
        return False
    # keypoints task have a slight different criteria for considering
    # if an annotation is valid
    if "keypoints" not in anno[0]:
        return True
    # for keypoint detection tasks, only consider valid images those
    # containing at least min_keypoints_per_image
    if _count_visible_keypoints(anno) >= min_keypoints_per_image:
        return True
    return False


class COCOYoloDataset:
    """YOLO Dataset for COCO."""

    def __init__(
            self,
            root,
            ann_file,
            input_size,
            remove_images_without_annotations=True,
            filter_crowd_anno=True,
            is_training=True,
        ):
        self.coco = COCO(ann_file)
        self.root = root
        self.img_ids = list(sorted(self.coco.imgs.keys()))
        self.filter_crowd_anno = filter_crowd_anno
        self.is_training = is_training
        self.mosaic = False
        self.input_size = input_size
        # filter images without any annotations
        if remove_images_without_annotations:
            img_ids = []
            for img_id in self.img_ids:
                ann_ids = self.coco.getAnnIds(imgIds=img_id, iscrowd=None)
                anno = self.coco.loadAnns(ann_ids)
                if has_valid_annotation(anno):
                    img_ids.append(img_id)
            self.img_ids = img_ids

        self.categories = {cat["id"]: cat["name"] for cat in self.coco.cats.values()}

        self.cat_ids_to_continuous_ids = {
            v: i for i, v in enumerate(self.coco.getCatIds())
        }
        self.continuous_ids_cat_ids = {
            v: k for k, v in self.cat_ids_to_continuous_ids.items()
        }
        self.count = 0

    def _mosaic_preprocess(self, index):
        """Mosaic preprocess"""
        labels4 = []
        s = 384
        mosaic_border = [-s // 2, -s // 2]
        yc, xc = [int(random.uniform(-x, 2 * s + x)) for x in mosaic_border]
        indices = [index] + [random.randint(0, len(self.img_ids) - 1) for _ in range(3)]
        for i, img_ids_index in enumerate(indices):
            coco = self.coco
            img_id = self.img_ids[img_ids_index]
            img_path = coco.loadImgs(img_id)[0]["file_name"]
            img = Image.open(os.path.join(self.root, img_path)).convert("RGB")
            img = np.array(img)
            h, w = img.shape[:2]

            if i == 0:  # top left
                img4 = np.full(
                    (s * 2, s * 2, img.shape[2]), 128, dtype=np.uint8
                )  # base image with 4 tiles
                x1a, y1a, x2a, y2a = (
                    max(xc - w, 0),
                    max(yc - h, 0),
                    xc,
                    yc,
                )  # xmin, ymin, xmax, ymax (large image)
                x1b, y1b, x2b, y2b = (
                    w - (x2a - x1a),
                    h - (y2a - y1a),
                    w,
                    h,
                )  # xmin, ymin, xmax, ymax (small image)
            elif i == 1:  # top right
                x1a, y1a, x2a, y2a = xc, max(yc - h, 0), min(xc + w, s * 2), yc
                x1b, y1b, x2b, y2b = 0, h - (y2a - y1a), min(w, x2a - x1a), h
            elif i == 2:  # bottom left
                x1a, y1a, x2a, y2a = max(xc - w, 0), yc, xc, min(s * 2, yc + h)
                x1b, y1b, x2b, y2b = w - (x2a - x1a), 0, w, min(y2a - y1a, h)
            elif i == 3:  # bottom right
                x1a, y1a, x2a, y2a = xc, yc, min(xc + w, s * 2), min(s * 2, yc + h)
                x1b, y1b, x2b, y2b = 0, 0, min(w, x2a - x1a), min(y2a - y1a, h)

            img4[y1a:y2a, x1a:x2a] = img[y1b:y2b, x1b:x2b]  # img4[ymin:ymax, xmin:xmax]

            padw = x1a - x1b
            padh = y1a - y1b

            ann_ids = coco.getAnnIds(imgIds=img_id)
            target = coco.loadAnns(ann_ids)
            # filter crowd annotations
            if self.filter_crowd_anno:
                annos = [anno for anno in target if anno["iscrowd"] == 0]
            else:
                annos = [anno for anno in target]

            target = {}
            boxes = [anno["bbox"] for anno in annos]
            target["bboxes"] = boxes

            classes = [anno["category_id"] for anno in annos]
            classes = [self.cat_ids_to_continuous_ids[cl] for cl in classes]
            target["labels"] = classes

            bboxes = target["bboxes"]
            labels = target["labels"]
            out_target = []

            for bbox, label in zip(bboxes, labels):
                tmp = []
                # convert to [x_min y_min x_max y_max]
                bbox = self.convet_top_down(bbox)
                tmp.extend(bbox)
                tmp.append(int(label))
                # tmp [x_min y_min x_max y_max, label]
                out_target.append(tmp)  # 这里out_target是label的实际宽高，对应于图片中的实际度量

            labels = out_target.copy()
            labels = np.array(labels)
            out_target = np.array(out_target)

            labels[:, 0] = out_target[:, 0] + padw
            labels[:, 1] = out_target[:, 1] + padh
            labels[:, 2] = out_target[:, 2] + padw
            labels[:, 3] = out_target[:, 3] + padh
            labels4.append(labels)

        if labels4:
            labels4 = np.concatenate(labels4, 0)
            np.clip(
                labels4[:, :4], 0, 2 * s, out=labels4[:, :4]
            )  # use with random_perspective
        flag = np.array([1])
        return img4, labels4, self.input_size, flag

    def __getitem__(self, index):
        """
        Args:
            index (int): Index

        Returns:
            (img, target) (tuple): target is a dictionary contains "bbox", "segmentation" or "keypoints",
                generated by the image's annotation. img is a PIL image.
        """
        coco = self.coco
        img_id = self.img_ids[index]
        img_path = coco.loadImgs(img_id)[0]["file_name"]
        if not self.is_training:
            img = Image.open(os.path.join(self.root, img_path)).convert("RGB")
            return img, img_id

        if self.mosaic and random.random() < 0.5:
            return self._mosaic_preprocess(index)
        img = np.fromfile(os.path.join(self.root, img_path), dtype="int8")
        ann_ids = coco.getAnnIds(imgIds=img_id)
        target = coco.loadAnns(ann_ids)
        # filter crowd annotations
        if self.filter_crowd_anno:
            annos = [anno for anno in target if anno["iscrowd"] == 0]
        else:
            annos = [anno for anno in target]

        target = {}
        boxes = [anno["bbox"] for anno in annos]
        target["bboxes"] = boxes

        classes = [anno["category_id"] for anno in annos]
        classes = [self.cat_ids_to_continuous_ids[cl] for cl in classes]
        target["labels"] = classes

        bboxes = target["bboxes"]
        labels = target["labels"]
        out_target = []
        for bbox, label in zip(bboxes, labels):
            tmp = []
            # convert to [x_min y_min x_max y_max]
            bbox = self.convet_top_down(bbox)
            tmp.extend(bbox)
            tmp.append(int(label))
            # tmp [x_min y_min x_max y_max, label]
            out_target.append(tmp)
        flag = np.array([0])
        return img, out_target, self.input_size, flag

    def __len__(self):
        return len(self.img_ids)

    def convet_top_down(self, bbox):
        """convert top down"""
        x_min = bbox[0]
        y_min = bbox[1]
        w = bbox[2]
        h = bbox[3]
        return [x_min, y_min, x_min + w, y_min + h]


def create_yolo_dataset(
        image_dir,
        anno_path,
        batch_size,
        max_epoch,
        device_num,
        rank,
        num_parallel_workers=8,
        config=None,
        is_training=True,
        shuffle=True,
    ):
    """Create dataset for YOLO."""
    cv2.setNumThreads(0)
    if config.is_distributed:
        de.config.set_enable_shared_mem(False)
    if is_training:
        filter_crowd = True
        remove_empty_anno = True
        input_size = [config.training_shape] * 2
    else:
        filter_crowd = False
        remove_empty_anno = False
        input_size = [config.testing_shape] * 2

    yolo_dataset = COCOYoloDataset(
        root=image_dir,
        ann_file=anno_path,
        input_size=input_size,
        filter_crowd_anno=filter_crowd,
        remove_images_without_annotations=remove_empty_anno,
        is_training=is_training,
    )
    distributed_sampler = DistributedSampler(
        len(yolo_dataset), device_num, rank, shuffle=shuffle
    )
    # 此行代码未通过审核：yolo_dataset.size = len(distributed_sampler)
    hwc_to_chw = CV.HWC2CHW()

    config.dataset_size = len(yolo_dataset)
    if is_training:
        multi_scale_trans = MultiScaleTrans(config, device_num)
        # 此行代码未通过审核：yolo_dataset.transforms = multi_scale_trans

        dataset_column_names = ["image", "annotation", "input_size", "mosaic_flag"]
        map1_out_column_names = ["image", "annotation", "size"]
        map2_in_column_names = ["annotation", "size"]
        map2_out_column_names = ["annotation", "bbox1", "bbox2", "gt_box1", "gt_box2"]

        ds = de.GeneratorDataset(
            yolo_dataset,
            column_names=dataset_column_names,
            sampler=distributed_sampler,
            python_multiprocessing=True,
            num_parallel_workers=num_parallel_workers,
        )
        ds = ds.map(
            operations=multi_scale_trans,
            input_columns=dataset_column_names,
            output_columns=map1_out_column_names,
            num_parallel_workers=16,
            python_multiprocessing=True,
        )
        ds = ds.map(
            operations=PreprocessTrueBox(config),
            input_columns=map2_in_column_names,
            output_columns=map2_out_column_names,
            num_parallel_workers=2,
            python_multiprocessing=False,
        )
        ds = ds.project(["image", "annotation", "bbox1", "bbox2", "gt_box1", "gt_box2"])
        mean = [m * 255 for m in [0.485, 0.456, 0.406]]
        std = [s * 255 for s in [0.229, 0.224, 0.225]]
        ds = ds.map([CV.Normalize(mean, std), hwc_to_chw], num_parallel_workers=2)
        ds = ds.batch(batch_size, num_parallel_workers=1, drop_remainder=True)
    else:
        ds = de.GeneratorDataset(
            yolo_dataset, column_names=["image", "img_id"], sampler=distributed_sampler
        )
        compose_map_func = lambda image, img_id: reshape_fn(image, img_id, config)
        ds = ds.map(
            operations=compose_map_func,
            input_columns=["image", "img_id"],
            output_columns=["image", "image_shape", "img_id"],
            num_parallel_workers=8,
        )
        ds = ds.map(
            operations=hwc_to_chw, input_columns=["image"], num_parallel_workers=8
        )
        ds = ds.batch(batch_size, drop_remainder=True)
    ds = ds.repeat(max_epoch)
    return ds, len(yolo_dataset)
