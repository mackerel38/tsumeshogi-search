# tsumeshogi-search

新作の通常詰将棋で1525手超えを目指す部品探索。**目標未達成。保存した長い経路は、強制された詰手数ではありません。**

[仕組みの設計](docs/MECHANISMS.md)と[ルール・検証範囲](docs/RULES.md)を基準にします。自玉なしの設計も対象です。ミクロコスモス1525手版の盤面・棋譜・改変図を探索種に含めません。

GHCRはPythonと将棋ライブラリの探索環境を配布し、GitHub Actionsのmatrixで最大6候補を並列探索します。最初の実装は協力的な盤面復元経路の探索です。詰み・最短手数・部品の強制の証明機能はまだ含みません。

## 実行

Actionsの `Parallel restoration search` を手動実行するか、タイトルが `[search]` で始まるIssueを作り、本文に以下を記載します。

```json
{"candidates":["horse-5d","horse-6c"],"seconds":60,"nodes":200000}
```

候補：`horse-8a`, `horse-7b`, `horse-6c`, `horse-5d`, `horse-1d`, `horse-4f`。Issueからの実行はOWNER/MEMBER/COLLABORATORに限定。秒数1〜600、追加局面数10〜1000000。Issue本文はJSON条件としてのみ読み、コードとして実行しません。

結果・圧縮チェックポイント・ログ・コミット/run番号は候補別Artifactsに30日保存します。時間・局面数の打切りはUNKNOWNであり、不成立の証明ではありません。

同じ探索を再開するには `"resume_run":123456789` を加えて、前回のActions run番号を指定します。同じ根局面・目標・探索方針かをコード内で検査します。FOUNDまたは探索完了のチェックポイントは再実行しません。

GHCRイメージはコミットSHAをタグにして記録します。Actionsの並列上限・実行時間はGitHub側の利用条件にも依存します。

## ローカル

```sh
pip install -r requirements.txt
python scripts/run_search.py --candidate horse-5d --seconds 5 --nodes 10000 --output results
```

候補003のSFENは `candidates/003-horse54-latent-check.sfen`。将棋ライブラリは固定バージョン、元の2.2GB研究ログは含めていません。
