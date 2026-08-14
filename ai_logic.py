from collections import defaultdict
import base64

from openai import OpenAI

from config import (
    AGNES_API_KEY,
    AGNES_BASE_URL,
    DEFAULT_MODEL,
    AVAILABLE_MODELS,
    VISION_MODEL,
)


# ============================================================
# Agnes Client
# ============================================================

client = OpenAI(
    api_key=AGNES_API_KEY,
    base_url=AGNES_BASE_URL
)


# ============================================================
# 用户模型
#
# 每个 Telegram 用户独立选择模型
# 不会因为一个人切换模型导致整个群一起切换
# ============================================================

user_models = defaultdict(
    lambda: DEFAULT_MODEL
)


# ============================================================
# 获取用户当前模型
# ============================================================

def get_user_model(user_id):

    return user_models[user_id]


# ============================================================
# 设置用户模型
# ============================================================

def set_user_model(
    user_id,
    model
):

    if model not in AVAILABLE_MODELS:

        return False

    user_models[user_id] = model

    return True


# ============================================================
# 调用 Agnes
# ============================================================

def ask_agnes(
    prompt: str,
    system_prompt: str = None,
    model: str = None
) -> str:

    if not model:

        model = DEFAULT_MODEL


    messages = []


    if system_prompt:

        messages.append({

            "role": "system",

            "content": system_prompt

        })


    messages.append({

        "role": "user",

        "content": prompt

    })


    response = client.chat.completions.create(

        model=model,

        messages=messages

    )


    if not response.choices:

        return "AI 没有返回有效结果。"


    content = response.choices[0].message.content


    if not content:

        return "AI 返回了空内容。"


    return content.strip()


# ============================================================
# 图片识别
# ============================================================

async def analyze_image(
    target_photo,
    user_prompt: str
):

    # --------------------------------------------------------
    # 下载图片
    # --------------------------------------------------------

    photo_file = await target_photo.get_file()

    image_bytes = await photo_file.download_as_bytearray()


    if not image_bytes:

        raise RuntimeError(
            "Telegram 图片下载失败。"
        )


    # --------------------------------------------------------
    # Base64
    # --------------------------------------------------------

    image_base64 = base64.b64encode(
        bytes(image_bytes)
    ).decode("utf-8")


    image_url = (
        "data:image/jpeg;base64,"
        + image_base64
    )


    # --------------------------------------------------------
    # 默认问题
    # --------------------------------------------------------

    if not user_prompt.strip():

        user_prompt = (

            "请详细分析这张图片。"

            "描述图片中的主要内容、人物、物体、环境，"

            "以及能够从图片中明确判断出的信息。"

            "不要凭空编造不存在的信息。"

        )


    # --------------------------------------------------------
    # 多模态请求
    # --------------------------------------------------------

    response = client.chat.completions.create(

        model=VISION_MODEL,

        messages=[

            {

                "role": "user",

                "content": [

                    {

                        "type": "text",

                        "text": user_prompt

                    },

                    {

                        "type": "image_url",

                        "image_url": {

                            "url": image_url

                        }

                    }

                ]

            }

        ]

    )


    if not response.choices:

        return "AI 没有返回图片分析结果。"


    reply = response.choices[0].message.content


    if not reply:

        return "AI 返回了空的图片分析结果。"


    return reply.strip()
