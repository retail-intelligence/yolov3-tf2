from absl import flags, app, logging
from typing import DefaultDict
import random
import os
import sys
import csv
import shutil
import xml.etree.ElementTree as ET

import config.create_set_config as config

FLAGS = flags.FLAGS

flags.DEFINE_string('set_name', None, 'Name of the new set')
flags.DEFINE_string(
    'previous_dataset', None, 'Path to Frozen dataset'
)

flags.mark_flag_as_required("set_name")


def main(argv) -> None:
    del argv

    set_files: list = []

    if not os.path.exists(os.path.join(config.set_output_folder, FLAGS.set_name)):
        create_set_folders()

    if not os.path.exists(str(FLAGS.previous_dataset)):
        create_empty_dataset()

    for _, _, files in os.walk(config.base_set_path, topdown=False):
        for file in files:
            if file.split('.')[1] == 'xml':
                set_files.append(file)

    persondet_dict: DefaultDict[str, str] = assign_set_to_persondet(set_files)

    for key in persondet_dict.keys():
        if os.path.exists(f'{config.base_set_path}/{key}') and os.path.exists(
            f'{config.base_set_path}/{key.split(".")[0]}.jpg'
        ):

            shutil.copy2(
                f'{config.base_set_path}/{key}',
                f'{config.set_output_folder}/{FLAGS.set_name}/{persondet_dict[key]}_label/{key}'
            )

            shutil.copy2(
                f'{config.base_set_path}/{key.split(".")[0]}.jpg',
                f'{config.set_output_folder}/{FLAGS.set_name}/{persondet_dict[key]}_data/{key.split(".")[0]}.jpg'
            )

    correct_xml_tree(persondet_dict)


def create_empty_dataset() -> None:

    FLAGS.previous_dataset = os.path.join(
        config.set_output_folder,
        FLAGS.set_name,
        config.frozen_set_name
    )

    with open(FLAGS.previous_dataset, 'w') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',')

        csv_writer.writerow(('persondet', 'set'))


def assign_set_to_persondet(persondet_path_list: list) -> dict:
    """Assign a set to each persondet path that doesn't have one.

    Compare the percentage of sets on the csv and assign the
    ones that weren't in the previous_dataset to a set according to the config
    defined percentage.

    Parameters
    ----------
    persondet_path_list : list
        List containing the path of the ids folders

    Returns
    -------
    dict
        Returns a dict with the key being the id and the values of each
        id the set of the id
    """
    csv_dict: DefaultDict[str, str] = DefaultDict(str)

    subtotal_train, subtotal_dev, subtotal_val, csv_id_list = get_csv_data(csv_dict)

    new_persondets: list = []
    for persondet_path in persondet_path_list:
        persondet = persondet_path.split('/')[-1]
        if persondet not in csv_id_list:
            new_persondets.append(persondet)

    subtotal_ids: int = 0
    # TODO this should accont in the future that each file can have more tha one id per file
    total_ids: int = len(persondet_path_list)

    subtotal_ids: int = subtotal_train + subtotal_dev + subtotal_val

    to_be_added: int = total_ids - subtotal_ids

    val_total: int = round(total_ids * config.set_val_percentage)
    dev_total: int = round(total_ids * config.set_dev_percentage)
    train_total: int = round(total_ids * config.set_train_percentage)

    val_total -= subtotal_val
    dev_total -= subtotal_dev
    train_total -= subtotal_train

    train_total += train_total + dev_total + val_total - to_be_added

    random.shuffle(new_persondets)

    if not os.path.exists(os.path.join(
        config.set_output_folder,
        FLAGS.set_name,
        config.frozen_set_name
    )):

        shutil.copy2(
            FLAGS.previous_dataset,
            os.path.join(config.set_output_folder, FLAGS.set_name, config.frozen_set_name)
        )

    add_to_dict_selected_persondet(new_persondets, csv_dict, 'dev_set', dev_total)
    add_to_dict_selected_persondet(new_persondets, csv_dict, 'val_set', val_total)
    add_to_dict_selected_persondet(new_persondets, csv_dict, 'train_set', train_total)

    return csv_dict


def add_to_dict_selected_persondet(
    new_persondets: list, csv_data: DefaultDict[str, str], set_name: str, ids_to_get: int
) -> None:
    """Select ids and assign the persondet to a set, adding them to the csv_data dict.

    Will select ids from the new id list and write them to the previous/new dataset.

    Parameters
    ----------
    new_persondets : list
        A list containing the names of new persondets added to this dataset
    csv_data : DefaultDict[str, str]
        Contains the data of the dataset, being the key the persondet and the value the
        set_name
    set_name : str
        The name of the set that the persondets will be assigned to
    ids_to_get : int
        The quantity of persondets to be added to the data set

    Returns
    -------
    None

    """
    new_persondet_list: list = new_persondets[:ids_to_get]
    del new_persondets[:ids_to_get]

    with open(
        os.path.join(config.set_output_folder, FLAGS.set_name, config.frozen_set_name),
        'a'
    ) as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',')

        for persondet in new_persondet_list:
            csv_writer.writerow((persondet, set_name))

    for persorndet in new_persondet_list:
        csv_data[persorndet]: str = set_name


def get_csv_data(csv_data: dict) -> (int, int, int, list):
    """Get data from the frozen set csv.

    Compare the percentage of sets on the csv and assign the
    ones that weren't in the previous_dataset to a set according to the config
    defined percentage.

    Parameters
    ----------
    csv_data : dict
        Empty dict that will receive the csv contents as the function reads

    Returns
    -------
    Tuple
        Containing:
        int
            The quantity of persondets in the train
        int
            The quantity of persondets in the dev
        int
            The quantity of persondets in the val
        list
            A list containing the persondets in the csv
    """
    csv_persondet_list: list = []
    subtotal_val: int = 0
    subtotal_dev: int = 0
    subtotal_train: int = 0

    with open(FLAGS.previous_dataset, 'r') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        next(csv_reader)
        for row in csv_reader:
            csv_data[row[0]] = row[1]
            csv_persondet_list.append(row[0])
            if row[1] == 'val_set':
                subtotal_val += 1
                continue
            if row[1] == 'dev_set':
                subtotal_dev += 1
                continue
            if row[1] == 'train_set':
                subtotal_train += 1

    return subtotal_train, subtotal_dev, subtotal_val, csv_persondet_list


def create_set_folders() -> None:
    """Create the folders necessary for the creation of the dataset.

    Create both folders data and label necessary for the three variations of sets that the
    persondet require

    Parameters
    ----------
    None

    Returns
    -------
    None

    """

    try:
        os.mkdir(os.path.join(config.set_output_folder, FLAGS.set_name))
        os.mkdir(os.path.join(config.set_output_folder, FLAGS.set_name, 'val_set_data'))
        os.mkdir(os.path.join(config.set_output_folder, FLAGS.set_name, 'val_set_label'))
        os.mkdir(os.path.join(config.set_output_folder, FLAGS.set_name, 'train_set_data'))
        os.mkdir(os.path.join(config.set_output_folder, FLAGS.set_name, 'train_set_label'))
        os.mkdir(os.path.join(config.set_output_folder, FLAGS.set_name, 'dev_set_label'))
        os.mkdir(os.path.join(config.set_output_folder, FLAGS.set_name, 'dev_set_data'))
    except Exception:
        logging.log(logging.FATAL, 'Could not create folders')


def correct_xml_tree(persondet_dict):

    persondet_paths = persondet_dict.keys()
    for persondet_path in persondet_paths:
        full_path = f'{config.set_output_folder}/{FLAGS.set_name}/{persondet_dict[persondet_path]}_label/{persondet_path}'
        tree = ET.parse(full_path)
        root = tree.getroot()

        for path in root.findall('path'):
            path.text = f'{config.set_xml_path}{FLAGS.set_name}/{persondet_dict[persondet_path]}_data/'

        for filename in root.findall('filename'):
            filename.text = f'{persondet_path.split(".")[0]}.jpg'

        for folder in root.findall('folder'):
            folder.text = f'{persondet_dict[persondet_path]}_data'

        tree._setroot(root)
        tree.write(full_path)


if __name__ == "__main__":
    app.run(main)
