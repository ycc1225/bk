from blueapps.utils import failed
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    自定义异常处理，返回统一的 JSON 格式
    {
        "result": False,
        "message": "错误信息",
        "data": {},
        "code": 状态码
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        message = "Error occurred"
        if isinstance(response.data, dict):
            if "detail" in response.data:
                message = response.data["detail"]
            else:
                # 处理参数校验错误，将所有错误拼接
                errors = []
                for field, msgs in response.data.items():
                    if isinstance(msgs, list):
                        errors.append(f"{field}: {'; '.join([str(m) for m in msgs])}")
                    else:
                        errors.append(f"{field}: {str(msgs)}")
                message = " | ".join(errors)
        elif isinstance(response.data, list):
            message = "; ".join([str(x) for x in response.data])
        else:
            message = str(response.data)

        response.data = failed(message=str(message), code=response.status_code)

    return response
