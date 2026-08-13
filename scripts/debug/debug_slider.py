import Grasshopper
import Grasshopper.Kernel as ghk

# 找到 Number Slider 的 proxy
server = Grasshopper.Instances.ComponentServer
slider_guid = "57da07bd-ecab-415d-9d86-af36d7073abc"
proxy = next((p for p in server.ObjectProxies if str(p.Guid).lower() == slider_guid), None)

obj = proxy.CreateInstance()
print(f"类型: {type(obj)}")
print(f"NickName: {obj.NickName}")

# 检查是否有 Slider 属性
print(f"hasattr Slider: {hasattr(obj, 'Slider')}")

# 列出所有不以 _ 开头的属性
attrs = [a for a in dir(obj) if not a.startswith('_')]
print(f"属性列表: {attrs}")

# 如果有 Slider 子属性
if hasattr(obj, 'Slider'):
    s = obj.Slider
    print(f"Slider 类型: {type(s)}")
    print(f"Slider 属性: {[a for a in dir(s) if not a.startswith('_')]}")
