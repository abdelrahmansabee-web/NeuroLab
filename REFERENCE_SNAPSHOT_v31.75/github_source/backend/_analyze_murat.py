import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from neuro_kinematics import analyze_patient_session

healthy = r'D:\Thesis app\participants\murat\healthy side.mp4'
post = r'D:\Thesis app\participants\murat\post.mp4'
pre = r'D:\Thesis app\participants\murat\pre.mp4'

print('Starting analysis...')
results, side_info = analyze_patient_session(healthy, post, pre)

print('\n=== Side Detection ===')
print(f"Affected side: {side_info.affected_side}")
print(f"Healthy side: {side_info.healthy_side}")
print(f"Confidence: {side_info.confidence}")
print(f"Left motion: {side_info.left_motion}")
print(f"Right motion: {side_info.right_motion}")

print('\n=== Kinematic Comparison ===')
for r in results:
    print(f"\n{r['variable']}:")
    print(f"  Pre:     {r['pre']}")
    print(f"  Post:    {r['post']}")
    print(f"  Healthy: {r['healthy']}")
    print(f"  {r['pre_to_post_str']}")
    print(f"  {r['post_to_healthy_str']}")

# Also save results to JSON
import json
out = {
    "side_detection": side_info.to_dict(),
    "comparison": results
}
with open(r'D:\Thesis app\participants\murat\kinematics_results.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('\nResults saved to: D:\\Thesis app\\participants\\murat\\kinematics_results.json')
