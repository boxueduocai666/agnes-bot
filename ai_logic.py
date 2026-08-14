import base64

from openai import OpenAI

from config import (
    AGNES_API_KEY,
    AGNES_BASE_URL,
    DEFAULT_MODEL,
    IMAGE_MODEL,
    CHAT_MODELS,
)


# ============================================================
# Agnes Client
# ============================================================

client = OpenAI(
    api_key=AGNES_API_KEY,
    base_url=AGNES_BASE_URL
)


# ============================================================
# 当前模型
#
# 每个用户可以独立选择模型。
# ============================================================

user_models = {}


# ============================================================
# 获取当前模型
# ============================================================

def get_user_model(user_id):

    return user_models.get(
        user_id,
        DEFAULT_MODEL
    )


# ============================================================
# 设置模型
# ============================================================

def set_user_model(
    user_id,
    model_name
):

    if model_name not in CHAT_MODELS:

        return False


    user_models[user_id] = model_name

    return True


# ============================================================
# 获取模型名称
# ============================================================

def get_model_display_name(model_name):

    if model_name in CHAT_MODELS:

        return CHAT_MODELS[model_name]["name"]


    return model_name


# ============================================================
# 普通 AI 对话
# ============================================================

def ask_agnes(
    prompt: str,
    user_id=None,
    system_prompt: str = None,
    model_name: str = None
) -> str:

    if model_name is None:

        if user_id is not None:

            model_name = get_user_model(
                user_id
            )

        else:

            model_name = DEFAULT_MODEL


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

        model=model_name,

        messages=messages

    )


    if not response.choices:

        return "AI 没有返回有效结果。"


    content = response.choices[0].message.content


    if not content:

        return "AI 返回了空内容。"


    return content.strip()


# ============================================================
# 图片理解
# ============================================================

async def analyze_image(
    target_photo,
    user_prompt: str,
    quote_context: str = ""
) -> str:

    # --------------------------------------------------------
    # 下载 Telegram 图片
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
    # 默认图片问题
    # --------------------------------------------------------

    if not user_prompt.strip():

        user_prompt = (
            "请详细分析这张图片。"
            "描述图片中的主要内容、人物、物体、环境，"
            "以及能够从图片中明确判断出的信息。"
            "不要凭空编造不存在的信息。"
        )


    if quote_context:

        user_prompt = (
            quote_context
            + "\n"
            + "用户的问题：\n"
            + user_prompt
        )


    # --------------------------------------------------------
    # 多模态请求
    # --------------------------------------------------------

    response = client.chat.completions.create(

        model=IMAGE_MODEL,

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
