import getpass
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class PersonalPathTests(unittest.TestCase):
    def test_tracked_documents_do_not_contain_this_user_path(self):
        user_name = getpass.getuser()
        forbidden = (
            f"C:\\Users\\{user_name}",
            f"C:/Users/{user_name}",
            f"/Users/{user_name}",
        )
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or "build" in path.parts or ".graphori" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for marker in forbidden:
                self.assertNotIn(marker, text, path)
            self.assertNotIn(user_name, text, path)


if __name__ == "__main__":
    unittest.main()
