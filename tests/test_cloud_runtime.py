import unittest
from unittest.mock import patch

from cloud_runtime import is_streamlit_community_cloud, trending_mode_cloud


class TestCloudRuntime(unittest.TestCase):
    def test_trending_mode_cloud(self):
        self.assertEqual(trending_mode_cloud(), "rss")

    @patch.dict("os.environ", {"FC_CLOUD": "1"}, clear=False)
    def test_fc_cloud_env(self):
        self.assertTrue(is_streamlit_community_cloud())

    @patch.dict("os.environ", {"FC_CLOUD": ""}, clear=False)
    @patch("cloud_runtime.Path")
    def test_not_cloud(self, path_cls):
        path_cls.return_value.is_dir.return_value = False
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(is_streamlit_community_cloud())


if __name__ == "__main__":
    unittest.main()
