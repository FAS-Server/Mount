# 设计思路

1. 如何重写mcdr配置？

    直接修改mcdr config, 然后使用`ServerInterface.get_plugin_command_source()`获取指令源，然后 `ServerInterface.execute_command("!!MCDR reload config")`进行配置重载

2. 如何修改/重写`server.properties`？
    
    引入`Jproperties`包
