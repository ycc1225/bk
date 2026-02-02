import logging

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class RecordUserBehaviorMiddleware(MiddlewareMixin):
    """
    自定义中间件-记录用户行为，进行埋点
    """

    def process_response(self, request, response):
        try:
            # 获取需要埋点存储的信息：用户名、请求的API名称、请求的API所属的类别（CMDB/JOB）

            # 路径格式：/api/cmdb/biz-list/ -> 提取类别为 cmdb，接口名为 biz-list
            # 路径格式：/api/job/backup-file/ -> 提取类别为 job，接口名为 backup-file
            path_clean = request.path.rstrip("/")

            # 分割路径并提取类别和接口名
            path_parts = path_clean.split("/")
            api_category = "Unknown"
            api_name = ""

            # 找到 'api' 的索引，并获取其后的部分
            try:
                api_index = path_parts.index("api")
                # 获取类别（api 后的第一部分）
                if api_index + 1 < len(path_parts):
                    api_category = path_parts[api_index + 1].upper()  # cmdb -> CMDB, job -> JOB
                # 获取接口名（api 后的第二部分）
                if api_index + 2 < len(path_parts):
                    api_name = path_parts[api_index + 2]
            except ValueError:
                pass

            # 判断是否为错误请求（4xx 或 5xx 状态码）或者返回码不为0
            is_error = response.status_code >= 400
            if not is_error:
                try:
                    if hasattr(response, "data") and isinstance(response.data, dict):
                        is_error = not response.data.get("result", True)
                except AttributeError as e:
                    is_error = True
                    logger.error(f"Unexpected Exception when get response data:{e}")

            from django.utils import timezone

            today = timezone.now().date()

            from home_application.utils.redis_utils import increment_api_count

            increment_api_count(api_category, api_name, today, is_error)
        except Exception as e:
            # 这里即使产生了异常，也应该继续往后执行，因为埋点记录不应该影响用户请求接口，应该是静默的，所以建议学有余力的同学尝试进行异步优化
            logger.exception(f"Unexpected Exception when record user behavior:{e}")
            pass
        return response
