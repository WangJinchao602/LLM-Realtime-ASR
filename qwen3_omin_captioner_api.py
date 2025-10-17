# import dashscope

# # 将 ABSOLUTE_PATH/welcome.mp3 替换为本地音频的绝对路径，
# # 本地文件的完整路径必须以 file:// 为前缀，以保证路径的合法性，例如：file:///home/images/test.mp3
# audio_file_path = "file://ABSOLUTE_PATH/welcome.mp3"
# messages = [
#     {
#         "role": "user",
#         # 在 audio 参数中传入以 file:// 为前缀的文件路径
#         "content": [{"audio": audio_file_path}],
#     }
# ]

# response = dashscope.MultiModalConversation.call(
#             model="qwen3-omni-30b-a3b-captioner",
#             messages=messages)
# print("输出结果为：")
# print(response["output"]["choices"][0]["message"].content[0]["text"])

import os
from openai import OpenAI
import base64

client = OpenAI(
    # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


def encode_audio(audio_path):
    with open(audio_path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode("utf-8")


# 请将 ABSOLUTE_PATH/welcome.mp3 替换为本地音频的绝对路径
audio_file_path = "xxx/ABSOLUTE_PATH/welcome.mp3"
base64_audio = encode_audio(audio_file_path)

completion = client.chat.completions.create(
    model="qwen3-omni-30b-a3b-captioner",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {
                        # 以 Base64 编码方式传入本地文件时，必须要以data:为前缀，以保证文件 URL 的合法性。
                        # 在 Base64 编码数据（base64_audio）前需要包含"base64"，否则也会报错。
                        "data": f"data:;base64,{base64_audio}"
                    },
                }
            ],
        },
    ]
)
print(completion.choices[0].message.content)

# import os
# from openai import OpenAI

# client = OpenAI(
#     # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
#     api_key="sk-2272144c861f44ea9a37c2868e07ba84",
#     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
# )

# completion = client.chat.completions.create(
#     model="qwen3-omni-30b-a3b-captioner",
#     messages=[
#         {
#             "role": "user",
#             "content": [
#                 {
#                     "type": "input_audio",
#                     "input_audio": {
#                         "data": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240916/xvappi/%E8%A3%85%E4%BF%AE%E5%99%AA%E9%9F%B3.wav"
#                     }
#                 }
#             ]
#         }
#     ]
# )
# print(completion.choices[0].message.content)

# 流式输出
# import os
# from openai import OpenAI

# client = OpenAI(
#     # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
#     api_key=os.getenv("DASHSCOPE_API_KEY"),
#     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
# )

# completion = client.chat.completions.create(
#     model="qwen3-omni-30b-a3b-captioner",
#     messages=[
#         {
#             "role": "user",
#             "content": [
#                 {
#                     "type": "input_audio",
#                     "input_audio": {
#                         "data": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240916/xvappi/%E8%A3%85%E4%BF%AE%E5%99%AA%E9%9F%B3.wav"
#                     }
#                 }
#             ]
#         }
#     ],
#     stream=True,
#     stream_options={"include_usage": True},

# )
# for chunk in completion:
#     # 如果stream_options.include_usage为True，则最后一个chunk的choices字段为空列表，需要跳过（可以通过chunk.usage获取 Token 使用量）
#     if chunk.choices and chunk.choices[0].delta.content != "":
#         print(chunk.choices[0].delta.content,end="")