"""Regression: standard tsume boards may omit the attacker's king."""
import unittest,shogi,cshogi
class OptionalKing(unittest.TestCase):
 def test_generation_and_check(self):
  s='8k/9/7R1/9/9/9/9/9/9 b r2b4g4s4n4l18p 1'
  a=shogi.Board(s);b=cshogi.Board(s)
  self.assertEqual({m.usi() for m in a.legal_moves},{cshogi.move_to_usi(m) for m in b.legal_moves})
  a.push_usi('2c1c');b.push_usi('2c1c')
  self.assertTrue(a.is_check());self.assertTrue(b.is_check())
  self.assertEqual({m.usi() for m in a.legal_moves},{cshogi.move_to_usi(m) for m in b.legal_moves})
if __name__=='__main__':unittest.main()
