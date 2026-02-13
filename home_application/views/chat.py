"""
ChatOps 对话视图

提供 POST /api/chatops/chat/ 接口，接收用户自然语言消息并返回 AI 回复。
"""

import logging

from blueapps.utils import ok_data
from rest_framework.response import Response
from rest_framework.views import APIView

from home_application.permission import IsDevOrAbove
from home_application.services.chatops import chatops_service

logger = logging.getLogger(__name__)


class ChatOpsView(APIView):
    """
    ChatOps 自然语言对话接口

    POST /api/chatops/chat/
    {
        "message": "最近有失败的备份作业吗？",
        "conversation_history": []  // 可选
    }
    """

    permission_classes = [IsDevOrAbove]

    def post(self, request):
        message = request.data.get("message", "").strip()
        conversation_history = request.data.get("conversation_history", [])

        # 参数校验
        if not message:
            return Response(
                {"result": False, "message": "消息内容不能为空", "code": "INVALID_PARAM"},
                status=400,
            )

        if len(message) > 500:
            return Response(
                {"result": False, "message": "消息长度不能超过500字符", "code": "INVALID_PARAM"},
                status=400,
            )

        if not isinstance(conversation_history, list):
            return Response(
                {"result": False, "message": "conversation_history 必须为数组格式", "code": "INVALID_PARAM"},
                status=400,
            )

        username = getattr(request.user, "username", "anonymous")
        logger.info("ChatOps 请求 | 用户=%s | 消息=%s", username, message[:100])

        try:
            result = chatops_service.chat(
                message=message,
                conversation_history=conversation_history,
            )
            return Response(ok_data(data=result))

        except ValueError as e:
            # 环境变量未配置等
            logger.error("ChatOps 配置错误: %s", e)
            return Response(
                {"result": False, "message": "AI 服务配置异常，请联系管理员", "code": "LLM_CONFIG_ERROR"},
                status=503,
            )

        except Exception as e:
            logger.exception("ChatOps 处理异常: %s", e)
            return Response(
                {"result": False, "message": "AI 服务暂时不可用，请稍后重试", "code": "LLM_UNAVAILABLE"},
                status=503,
            )
