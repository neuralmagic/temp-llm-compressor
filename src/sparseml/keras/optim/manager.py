"""
Contains base code related to modifier managers: modifier managers handle
grouping modifiers and running them together.
Also handles loading modifiers from yaml files
"""

from typing import List, Union

import tensorflow as tf

from sparseml.keras.optim.modifier import Modifier, ScheduledModifier
from sparseml.keras.utils.logger import KerasLogger
from sparseml.optim import BaseManager
from sparseml.utils import load_recipe_yaml_str


__all__ = ["ScheduledModifierManager"]


class ScheduledModifierManager(BaseManager, Modifier):
    """
    The base modifier manager, handles managing multiple ScheduledModifier.
    """

    @staticmethod
    def from_yaml(file_path: str, add_modifiers: List[Modifier] = None):
        """
        Convenience function used to create the manager of multiple modifiers
        from a yaml file.

        :param file_path: the path to the yaml file to load the modifier from
        :param add_modifiers: additional modifiers that should be added to the
            returned manager alongside the ones loaded from the yaml file
        :return: ScheduledModifierManager() created from the yaml file
        """
        yaml_str = load_recipe_yaml_str(file_path)
        modifiers = Modifier.load_list(yaml_str)
        if add_modifiers:
            modifiers.extend(add_modifiers)

        manager = ScheduledModifierManager(modifiers)

        return manager

    def __init__(self, modifiers: List[ScheduledModifier]):
        super().__init__(modifiers=modifiers)
        self._optimizer = None

    def modify(
        self,
        model: Union[tf.keras.Model, tf.keras.Sequential],
        optimizer: tf.keras.optimizers.Optimizer,
        steps_per_epoch: int,
        loggers: Union[KerasLogger, List[KerasLogger]] = None,
        input_tensors: tf.Tensor = None,
    ):
        """
        Modify the model and optimizer based on the requirements of modifiers

        :param model: model to modify
        :param optimizer: optimizer to modify
        :param steps_per_epoch: number of steps per epoch
        :param loggers: list of loggers
        :param input_tensors: optional input tensor
        :return: model, optimizer, callbacks
        """

        # Different modifiers might have logging callbacks a same global variables,
        # thus modifiers need to be sorted increasing based on their start steps to
        # make sure logging on shared variables reflect the latest effect
        self._modifiers.sort(key=lambda mod: mod.start_epoch)

        callbacks = []
        for mod in self._modifiers:
            model, optimizer, callback = mod.modify(
                model,
                optimizer,
                steps_per_epoch,
                loggers=loggers,
                input_tensors=input_tensors,
            )
            if callback is None:
                continue
            if isinstance(callback, list):
                callbacks = callbacks + callback
            elif isinstance(callback, tf.keras.callbacks.Callback):
                callbacks.append(callback)
            else:
                raise RuntimeError("Invalid callback type")
        self._optimizer = optimizer
        return model, optimizer, callbacks

    def finalize(self, model: tf.keras.Model):
        """
        Remove extra information related to the modifier from the model that is
        not necessary for exporting

        :param model: a Keras model
        :return: a new Keras model
        """
        for mod in self._modifiers:
            model = mod.finalize(model)
        return model