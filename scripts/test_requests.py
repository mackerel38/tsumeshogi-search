import unittest
from plan import request
class RequestTests(unittest.TestCase):
 def test_valid(self):
  self.assertEqual(len(request('```json\n{"candidates":["horse-5d","horse-6c"],"resume_run":123}\n```')['include']),2)
 def test_untrusted(self):
  for value in ['{"candidates":["$(id)"]}','{"seconds":99999}','{"nodes":true}','{"candidates":["horse-5d","horse-5d"]}','{"command":"id"}']:
   with self.subTest(value=value),self.assertRaises((AssertionError,ValueError,TypeError)):request(value)
if __name__=='__main__':unittest.main()
