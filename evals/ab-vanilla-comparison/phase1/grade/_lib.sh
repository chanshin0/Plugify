# 공용: ok/fail 출력 + 카운트
PASS=0; FAIL=0; NA=0
ok(){ PASS=$((PASS+1)); echo "ok   $*"; }
fail(){ FAIL=$((FAIL+1)); echo "FAIL $*"; }
na(){ NA=$((NA+1)); echo "n/a  $*"; }
summary(){ echo "--- $PASS ok / $FAIL FAIL / $NA n/a (manual items graded separately from final.md)"; }
