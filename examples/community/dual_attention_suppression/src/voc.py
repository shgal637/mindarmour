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

"""xml convert to coco"""

import glob
import json
import os
import stat
import xml.etree.ElementTree as ET
import numpy as np

define_categories = {"with_mask": 1, "without_mask": 2, "mask_weared_incorrect": 3}
anno_train_dir = "../dataset/train/annotations"
anno_val_dir = "../dataset/val/annotations"
save_dir = "../dataset/annotations_json"
if not os.path.exists(save_dir):
    os.makedirs(save_dir)


def convert(xml_list, json_file):
    """Convert."""
    json_dict = {"images": [], "type": "instances", "annotations": [], "categories": []}
    categories = define_categories.copy()
    bnd_id = 1

    for line in xml_list:
        xml_f = line
        tree = ET.parse(xml_f)
        root = tree.getroot()

        filename = root.find("filename").text[:-4] + ".jpg"

        image_id = int(filename[12:-4])  # maksssksksss 12
        size = root.find("size")
        width = int(size.find("width").text)
        height = int(size.find("height").text)
        image = {
            "file_name": filename,
            "height": height,
            "width": width,
            "id": image_id,
        }
        json_dict["images"].append(image)

        for obj in root.findall("object"):
            category = obj.find("name").text
            if category not in categories:
                continue
            category_id = categories[category]
            bndbox = obj.find("bndbox")
            xmin = int(float(bndbox.find("xmin").text)) - 1
            ymin = int(float(bndbox.find("ymin").text)) - 1
            xmax = int(float(bndbox.find("xmax").text)) - 1
            ymax = int(float(bndbox.find("ymax").text)) - 1
            assert xmax > xmin, "xmax <= xmin, {}".format(line)
            assert ymax > ymin, "ymax <= ymin, {}".format(line)
            o_width = abs(xmax - xmin)
            o_height = abs(ymax - ymin)
            ann = {
                "area": o_width * o_height,
                "iscrowd": 0,
                "image_id": image_id,
                "bbox": [xmin, ymin, o_width, o_height],
                "category_id": category_id,
                "id": bnd_id,
                "segmentation": [],
            }  # Currently we do not support segmentation
            json_dict["annotations"].append(ann)
            bnd_id = bnd_id + 1

    for cate_name, cid in categories.items():
        cat = {"supercategory": "none", "id": cid, "name": cate_name}
        json_dict["categories"].append(cat)
    with os.fdopen(
            os.open(json_file, flags=os.O_WRONLY, modes=stat.S_IWUSR, mode=0o777), "w"
        ) as json_fp:
        json_str = json.dumps(json_dict)
        json_fp.write(json_str)
    print("------------create {} done--------------".format(json_file))
    print("category: id --> {}".format(categories))
    print(categories.keys())
    print(categories.values())


if __name__ == "__main__":
    anno_train_list = glob.glob(anno_train_dir + "/*.xml")
    anno_train_list = np.sort(anno_train_list)

    anno_val_list = glob.glob(anno_val_dir + "/*.xml")
    anno_val_list = np.sort(anno_val_list)

    # save json files
    save_anno_train = save_dir + "/train.json"
    save_anno_val = save_dir + "/val.json"

    convert(anno_train_list, save_anno_train)
    convert(anno_val_list, save_anno_val)
