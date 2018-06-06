import unittest
from application import Storage

class TestSuite(unittest.TestCase):
  def test(self):
    storage = Storage()
    storage.populate()
    name = storage.name()
    self.failIf(name != "Johnny")

def main():
  unittest.main()

if __name__ == "__main__":
  main()
