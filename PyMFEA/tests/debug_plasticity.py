"""
深度诊断塑性收敛问题
"""
import numpy as np
np.set_printoptions(precision=4, suppress=True)

from core.materials import J2PlasticMaterial, PlasticState
from core.materials.elastic.isotropic import IsotropicElastic
from core.materials.plastic.yield_functions import VonMises
from core.materials.plastic.hardening import PerfectPlasticity
from core.materials.plastic.return_mapping import RadialReturn

print("=" * 60)
print("塑性收敛问题深度诊断")
print("=" * 60)

# 材料参数
E, nu, sigma_y = 70000.0, 0.3, 6.0
print(f"\n[材料参数] E={E}, nu={nu}, sigma_y={sigma_y}")

# 创建组件
elastic = IsotropicElastic(E, nu)
yield_fn = VonMises()
hardening = PerfectPlasticity(sigma_y)
rm = RadialReturn(elastic, yield_fn, hardening)

print(f"  mu = {elastic.mu:.2f}")
print(f"  K = {elastic.K:.2f}")

# === 测试1: 刚超过屈服 ===
print("\n" + "=" * 60)
print("测试1: 刚超过屈服的单轴应力状态")
print("=" * 60)

# 试探应力 (略超过屈服)
stress_trial = np.array([8.0, 0, 0, 0, 0, 0])  # sigma_xx = 8 > 6
print(f"试探应力: {stress_trial}")
print(f"Von Mises 等效应力: {yield_fn.equivalent_stress(stress_trial):.4f}")
print(f"屈服应力: {sigma_y}")

# 返回映射
stress, tangent, ep_new, is_plastic = rm.apply(stress_trial, 0.0)
print(f"\n返回映射后:")
print(f"  应力: {stress}")
print(f"  等效塑性应变: {ep_new:.6f}")
print(f"  是否塑性: {is_plastic}")

# 检查返回后的 Von Mises
sigma_eq_after = yield_fn.equivalent_stress(stress)
print(f"  返回后 Von Mises 应力: {sigma_eq_after:.4f}")
print(f"  差值 (应接近0): {abs(sigma_eq_after - sigma_y):.6f}")

# === 测试2: 一致切线模量 ===
print("\n" + "=" * 60)
print("测试2: 一致切线模量检查")
print("=" * 60)

print(f"弹性刚度矩阵 D 对角线: {np.diag(elastic.D)}")
print(f"一致切线 D_tang 对角线: {np.diag(tangent)}")
print(f"切线是否正定: {np.all(np.linalg.eigvals(tangent) > 0)}")
print(f"切线最小特征值: {np.min(np.linalg.eigvals(tangent)):.2f}")

# === 测试3: 多次增量 ===
print("\n" + "=" * 60)
print("测试3: 塑性增量累积测试")
print("=" * 60)

ep = 0.0
for i in range(5):
    stress_t = np.array([10.0 + i*2, 0, 0, 0, 0, 0])
    stress, tangent, ep, is_plastic = rm.apply(stress_t, ep)
    print(f"  增量{i+1}: trial_sigma={stress_t[0]:.1f}, sigma={stress[0]:.4f}, ep={ep:.6f}, plastic={is_plastic}")

# === 测试4: 完整材料模型 ===
print("\n" + "=" * 60)
print("测试4: 完整 J2PlasticMaterial 测试")
print("=" * 60)

mat = J2PlasticMaterial(E, nu, sigma_y)
state = mat.create_state()

# 施加变形
for i in range(5):
    strain = 0.0002 * (i + 1)  # 0.02%, 0.04%, ...
    F = np.eye(3) + np.array([[strain, 0, 0], [0, -nu*strain, 0], [0, 0, -nu*strain]])
    
    result = mat.compute_stress(F, state)
    state = result.state  # 更新状态
    
    print(f"  步{i+1}: strain={strain*100:.3f}%, sigma_xx={result.stress[0]:.4f}, ep={result.state.equivalent_plastic_strain:.6f}, plastic={result.is_plastic}")

print("\n诊断完成。")
