"""
内置扩展插件包

框架自带的业务扩展（tools / resources / prompts），
通过 discovery_paths 中的 "src.plugins.builtin" 被插件系统扫描注册。
与机制层（collector / discovery / manager / registry）隔离：
机制层永不参与扫描，本包是唯一被扫描的内容区。
"""
