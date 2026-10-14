# tsumeshogi-search

新作の通常詰将棋で1525手超えを目指す部品探索。**目標未達成。保存した長い経路は、強制された詰手数ではありません。**

[仕組みの設計](docs/MECHANISMS.md)と[ルール・検証範囲](docs/RULES.md)を基準にします。自玉なしの設計も対象です。ミクロコスモス1525手版の盤面・棋譜・改変図を探索種に含めません。

GHCRはPythonと将棋ライブラリの探索環境を配布し、GitHub Actionsのmatrixで最大6候補を並列探索します。最初の実装は協力的な盤面復元経路の探索です。詰み・最短手数・部品の強制の証明機能はまだ含みません。

## 実行

Actionsの `Parallel restoration search` を手動実行するか、タイトルが `[search]` で始まるIssueを作り、本文に以下を記載します。

```json
{"candidates":["horse-5d","horse-6c"],"seconds":60,"nodes":200000}
```

候補：`horse-8a`, `horse-7b`, `horse-6c`, `horse-5d`, `horse-1d`, `horse-4f`, `no-king-core`。Issueからの実行はOWNER/MEMBER/COLLABORATORに限定。秒数1〜600、追加局面数10〜1000000。Issue本文はJSON条件としてのみ読み、コードとして実行しません。

結果・圧縮チェックポイント・ログ・コミット/run番号は候補別Artifactsに30日保存します。時間・局面数の打切りはUNKNOWNであり、不成立の証明ではありません。

同じ探索を再開するには `"resume_run":123456789` を加えて、前回のActions run番号を指定します。同じ根局面・目標・探索方針かをコード内で検査します。FOUNDまたは探索完了のチェックポイントは再実行しません。

GHCRイメージはコミットSHAをタグにして記録します。Actionsの並列上限・実行時間はGitHub側の利用条件にも依存します。

## ローカル

```sh
pip install -r requirements.txt
python scripts/run_search.py --candidate horse-5d --seconds 5 --nodes 10000 --output results
```

候補003のSFENは `candidates/003-horse54-latent-check.sfen`。将棋ライブラリは固定バージョン、元の2.2GB研究ログは含めていません。

自玉なしの新しい核は `candidates/004-no-king-transfer-core.sfen`。馬と自玉を外しても86手の選択経路は成立するが、詰みと強制は未証明。

## 検証済みの位置送り部品

`candidates/007-pawn-lance-rail-step.sfen` は盤上5枚、自玉なし。左右の香で通路を作り、後方の香で歩を守る。歩と玉が一段ずつ進む最短11手を、9手以内の詰みがない証明と11手以内の詰みがある証明で確認した。全王手と必要な玉方応手を両ライブラリで照合する。これは長手数作品の完成ではなく、内側の処理に接続する前の位置送り部品。

再現：`python research/bounded_mate_component.py`。証拠：`candidates/007-exact11-proof.json`。無駄合に依存しない玉の逃げで9手以内の詰みを否定し、歩の接触王手で11手以内の詰みを証明する。反復はない。全余詰の検査は未完了。

空間・駒種変換の実験候補：`spatial-pawn37-38`, `spatial-lance68-67`, `spatial-silver62-promote`, `spatial-pawn26-demote`。各候補の `-target.json` は、持駒を変えず盤面の一箇所だけを変える出口条件。選択経路・強制とも未成立。

## 棄却した初形004

004/no-king-coreの初形は不詰を独立検証しました。全攻方王手を含む27局面・28辺の玉方戦略が閉じ、詰みに至りません。初手の王手２種類（飛24xと26、金47x歩37）には、いずれも玉27→18を選ぶ戦略があります。再現：`python scripts/verify_nomate.py candidates/004-nomate-certificate.json`。初形004からの変換経路は部品の協力実験であり、完成作品の候補としては棄却します。

## 資源不足状態の不詰探索

`safety.yml` は歩一枚の入口について、保存済みの約15万局面のグラフから二種類の玉方応手優先順で探索を再開します。GHCRイメージを使用し、結果は `safety-{policy}-{run_id}` に圧縮チェックポイントとして保存します。これは長い協力手順の探索とは別で、全攻方王手に対して玉方が逃れ続ける戦略を探すものです。

`UNKNOWN` は予算内で結論が出なかったことを示します。エンジンの不詰報告は証明葉に使用しません。閉じた不詰戦略はPython側の手生成で独立検証します。合駒を使う証明が得られた場合は、通常詰将棋への適用前に無駄合の監査が別途必要です。有限詰を発見した場合も、独立した詰み証明の検証前は未検証と表示します。

歩ゼロの入口には1190局面の不詰証明があります。玉方の選択応手は全て玉の移動で、合駒に依存しません。再現：`python scripts/verify_nomate.py candidates/safety/pawn2-stock0-certificate.json`。歩一枚の不詰、二枚を必須とする閾値、反復・復元機構はいずれも未完成です。

`orthodox_legal.py` は打歩詰判定で、ピンされた駒の捕獲を逃れと誤認しないよう、実際に自玉が安全な応手を列挙します。`scripts/check_pawn_drop_rule.py` は禁止される歩打ち、許される盤上歩の前進、逃げ道のある歩打ちをnative側と照合します。

不詰証明を27局面へ簡約しました。唯一の選択された合駒△１八歩は、攻方飛に取らせて玉がその飛を取るためのものです。遠い合駒を重ねる旧証明から置き換えました。閉じた戦略には循環もありますが、王手を続けて循環する攻方は有限の詰みに至れません。
