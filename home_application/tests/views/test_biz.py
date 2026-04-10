"""
Biz视图单元测试
"""

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from home_application.models import BizInfo

User = get_user_model()


class TestBizInfoViewSet(APITestCase):
    """测试 BizInfoViewSet"""

    def setUp(self):
        self.client = APIClient()
        # 创建测试数据
        self.biz1 = BizInfo.objects.create(bk_biz_id=1, bk_biz_name="业务A")
        self.biz2 = BizInfo.objects.create(bk_biz_id=2, bk_biz_name="业务B")
        self.biz3 = BizInfo.objects.create(bk_biz_id=3, bk_biz_name="业务C")

    def test_list_biz(self):
        """测试：获取业务列表"""
        response = self.client.get("/api/cmdb/biz-list/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["result"])
        self.assertIn("info", response.data["data"])
        self.assertEqual(len(response.data["data"]["info"]), 3)

    def test_list_biz_ordering(self):
        """测试：业务列表按bk_biz_id排序"""
        BizInfo.objects.create(bk_biz_id=10, bk_biz_name="业务Z")
        BizInfo.objects.create(bk_biz_id=5, bk_biz_name="业务M")

        response = self.client.get("/api/cmdb/biz-list/")

        self.assertEqual(response.status_code, 200)
        info = response.data["data"]["info"]
        bk_biz_ids = [b["bk_biz_id"] for b in info]
        self.assertEqual(bk_biz_ids, sorted(bk_biz_ids))

    def test_retrieve_nonexistent_biz(self):
        """测试：获取不存在的业务"""
        response = self.client.get("/api/cmdb/biz-list/99999/")

        self.assertEqual(response.status_code, 404)

    def test_list_empty_biz(self):
        """测试：空业务列表"""
        BizInfo.objects.all().delete()

        response = self.client.get("/api/cmdb/biz-list/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]["info"]), 0)
