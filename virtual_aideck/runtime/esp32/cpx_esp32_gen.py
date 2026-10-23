from generators.v1.comp_gen import *
from collections import OrderedDict


def gen_config(name, system_config, system, device_config, usecases=[]):
    """Bind SPI1/CS0 plus both real AI-deck ready-to-talk GPIOs."""
    itf = device_config.get_str('interface')
    cs = device_config.get_str('cs')

    system.system_tree.board.add_component(name, Tb_Component(
        config=device_config.get('config'),
        properties=OrderedDict([('name', name)])))

    gpio_ready = device_config.get_child_str('gpio_ready')
    gpio_notify = device_config.get_child_str('gpio_notify')

    system.system_tree.board.chip.set(
        gpio_ready, system.system_tree.board.dpi.new_itf(gpio_ready))
    system.system_tree.board.chip.set(
        gpio_ready, system.system_tree.board.get(name).new_itf('gpio_ready'))

    system.system_tree.board.chip.set(
        gpio_notify, system.system_tree.board.dpi.new_itf(gpio_notify))
    system.system_tree.board.chip.set(
        gpio_notify, system.system_tree.board.get(name).new_itf('gpio_notify'))

    data_port = itf + '_cs' + str(cs) + '_data'
    cs_port = itf + '_cs' + str(cs)
    system.system_tree.board.chip.set(
        data_port, system.system_tree.board.dpi.new_itf(data_port))
    system.system_tree.board.chip.set(
        cs_port, system.system_tree.board.dpi.new_itf(cs_port))
    system.system_tree.board.chip.set(
        data_port, system.system_tree.board.get(name).input)
