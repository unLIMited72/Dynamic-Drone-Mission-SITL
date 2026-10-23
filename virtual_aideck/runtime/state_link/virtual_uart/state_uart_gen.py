from generators.v1.comp_gen import Component,OrderedDict

def gen_config(name,system_config,system,device_config,usecases=[]):
    board=system.system_tree.board
    board.add_component(name,Component(properties=OrderedDict([('vp_component','state_uart')])) )
    board.add_component('state_uart_clock',Component(properties=OrderedDict([('vp_component','vp.clock_domain_impl'),('frequency',50000000)])))
    board.state_uart_clock.out=board.get(name).new_itf('clock')
    board.chip.set('uart0',board.get(name).new_itf('input'))
