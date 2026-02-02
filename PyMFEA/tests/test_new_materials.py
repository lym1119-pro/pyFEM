# 文件: PyMFEA/tests/test_new_materials.py
"""
新材料系统单元测试
"""

import sys
sys.path.insert(0, 'PyMFEA')

import numpy as np
import pytest
from core.materials import (
    MaterialFactory, 
    PlasticState, 
    J2PlasticMaterial,
    IsotropicElastic,
    VonMises,
    PerfectPlasticity,
    LinearIsotropicHardening,
    RadialReturn,
    tensor_to_voigt,
    voigt_to_tensor,
)


class TestIsotropicElastic:
    """测试各向同性弹性模型"""
    
    def test_elastic_matrix_symmetry(self):
        """测试弹性矩阵对称性"""
        elastic = IsotropicElastic(E=210e9, nu=0.3)
        D = elastic.D
        assert np.allclose(D, D.T), "弹性矩阵应对称"
    
    def test_elastic_matrix_positive_definite(self):
        """测试弹性矩阵正定性"""
        elastic = IsotropicElastic(E=210e9, nu=0.3)
        eigenvalues = np.linalg.eigvals(elastic.D)
        assert np.all(eigenvalues > 0), "弹性矩阵应正定"
    
    def test_uniaxial_stress(self):
        """测试单轴应力状态"""
        E, nu = 210e9, 0.3
        elastic = IsotropicElastic(E=E, nu=nu)
        
        # 单轴应变
        strain = np.array([0.001, 0, 0, 0, 0, 0])
        stress, _ = elastic.compute_stress(strain)
        
        # σ_xx ≈ E * ε_xx (近似，忽略泊松效应)
        # 精确: σ_xx = E*(1-ν)/((1+ν)(1-2ν)) * ε_xx
        expected_factor = E * (1 - nu) / ((1 + nu) * (1 - 2 * nu))
        assert np.isclose(stress[0], expected_factor * 0.001, rtol=1e-10)
    
    def test_shear_modulus(self):
        """测试剪切模量"""
        E, nu = 210e9, 0.3
        elastic = IsotropicElastic(E=E, nu=nu)
        expected_mu = E / (2 * (1 + nu))
        assert np.isclose(elastic.mu, expected_mu)
    
    def test_bulk_modulus(self):
        """测试体积模量"""
        E, nu = 210e9, 0.3
        elastic = IsotropicElastic(E=E, nu=nu)
        expected_K = E / (3 * (1 - 2 * nu))
        assert np.isclose(elastic.K, expected_K)


class TestVonMises:
    """测试 Von Mises 屈服函数"""
    
    def test_uniaxial_yield(self):
        """测试单轴屈服"""
        yield_fn = VonMises()
        yield_stress = 250e6
        
        # 正好屈服
        stress = np.array([250e6, 0, 0, 0, 0, 0])
        f = yield_fn.evaluate(stress, yield_stress)
        assert np.isclose(f, 0, atol=1e-3)
    
    def test_hydrostatic_no_yield(self):
        """测试静水压力不屈服"""
        yield_fn = VonMises()
        yield_stress = 250e6
        
        # 高静水压力
        stress = np.array([1e9, 1e9, 1e9, 0, 0, 0])
        f = yield_fn.evaluate(stress, yield_stress)
        assert f < 0, "纯静水压力不应屈服"
    
    def test_equivalent_stress(self):
        """测试等效应力计算"""
        yield_fn = VonMises()
        
        # 单轴拉伸
        stress = np.array([300e6, 0, 0, 0, 0, 0])
        sigma_eq = yield_fn.equivalent_stress(stress)
        assert np.isclose(sigma_eq, 300e6, rtol=1e-10)
        
        # 纯剪切 (σ_xy)
        stress = np.array([0, 0, 0, 0, 0, 150e6])
        sigma_eq = yield_fn.equivalent_stress(stress)
        expected = np.sqrt(3) * 150e6  # σ_eq = √3 * τ
        assert np.isclose(sigma_eq, expected, rtol=1e-10)
    
    def test_gradient_normalization(self):
        """测试梯度归一化"""
        yield_fn = VonMises()
        stress = np.array([300e6, -100e6, 50e6, 10e6, 20e6, 30e6])
        n = yield_fn.gradient(stress)
        
        # 梯度应非零
        assert np.linalg.norm(n) > 0


class TestHardening:
    """测试硬化模型"""
    
    def test_perfect_plasticity(self):
        """测试理想塑性"""
        h = PerfectPlasticity(yield_stress=250e6)
        
        assert h.get_yield_stress(0.0) == 250e6
        assert h.get_yield_stress(0.1) == 250e6
        assert h.get_hardening_modulus(0.0) == 0.0
    
    def test_linear_hardening(self):
        """测试线性硬化"""
        h = LinearIsotropicHardening(yield_stress=250e6, H=1e9)
        
        assert h.get_yield_stress(0.0) == 250e6
        assert h.get_yield_stress(0.1) == 250e6 + 1e9 * 0.1
        assert h.get_hardening_modulus(0.0) == 1e9


class TestRadialReturn:
    """测试径向返回算法"""
    
    def setup_method(self):
        """测试准备"""
        self.elastic = IsotropicElastic(E=210e9, nu=0.3)
        self.yield_fn = VonMises()
        self.hardening = PerfectPlasticity(yield_stress=250e6)
        self.return_mapping = RadialReturn(
            self.elastic, self.yield_fn, self.hardening
        )
    
    def test_elastic_response(self):
        """测试弹性响应"""
        stress_trial = np.array([200e6, 0, 0, 0, 0, 0])
        stress, tangent, ep_new, is_plastic = self.return_mapping.apply(
            stress_trial, ep_old=0.0
        )
        
        assert not is_plastic
        assert np.allclose(stress, stress_trial)
        assert ep_new == 0.0
    
    def test_plastic_response(self):
        """测试塑性响应"""
        stress_trial = np.array([400e6, 0, 0, 0, 0, 0])
        stress, tangent, ep_new, is_plastic = self.return_mapping.apply(
            stress_trial, ep_old=0.0
        )
        
        assert is_plastic
        assert ep_new > 0.0
        
        # 返回后应力应在屈服面上
        sigma_eq = self.yield_fn.equivalent_stress(stress)
        assert np.isclose(sigma_eq, 250e6, rtol=1e-6)


class TestJ2PlasticMaterial:
    """测试 J2 弹塑性材料"""
    
    def test_elastic_deformation(self):
        """测试弹性变形"""
        mat = J2PlasticMaterial(E=210e9, nu=0.3, yield_stress=250e6)
        state = mat.create_state()
        
        # 小变形
        F = np.eye(3) + 0.0001 * np.diag([1, -0.3, -0.3])
        result = mat.compute_stress(F, state)
        
        assert not result.is_plastic
        assert result.state.equivalent_plastic_strain == 0.0
    
    def test_plastic_deformation(self):
        """测试塑性变形"""
        mat = J2PlasticMaterial(E=210e9, nu=0.3, yield_stress=250e6)
        state = mat.create_state()
        
        # 大变形
        F = np.eye(3) + 0.01 * np.diag([1, -0.3, -0.3])
        result = mat.compute_stress(F, state)
        
        assert result.is_plastic
        assert result.state.equivalent_plastic_strain > 0.0
    
    def test_state_immutability(self):
        """测试状态不可变性"""
        mat = J2PlasticMaterial(E=210e9, nu=0.3, yield_stress=250e6)
        state = mat.create_state()
        original_ep = state.equivalent_plastic_strain
        
        F = np.eye(3) + 0.01 * np.diag([1, -0.3, -0.3])
        result = mat.compute_stress(F, state)
        
        # 原始状态不应被修改
        assert state.equivalent_plastic_strain == original_ep
        # 返回的新状态应被更新
        assert result.state.equivalent_plastic_strain > original_ep
    
    def test_tangent_symmetry(self):
        """测试切线模量对称性"""
        mat = J2PlasticMaterial(E=210e9, nu=0.3, yield_stress=250e6)
        state = mat.create_state()
        
        F = np.eye(3) + 0.005 * np.diag([1, -0.3, -0.3])
        result = mat.compute_stress(F, state)
        
        assert np.allclose(result.tangent, result.tangent.T), "切线模量应对称"


class TestMaterialFactory:
    """测试材料工厂"""
    
    def test_create_elastic(self):
        """测试创建弹性材料"""
        mat = MaterialFactory.create_elastic(E=210e9, nu=0.3)
        assert isinstance(mat, J2PlasticMaterial)
    
    def test_create_j2_plastic(self):
        """测试创建 J2 塑性材料"""
        mat = MaterialFactory.create_j2_plastic(
            E=210e9, nu=0.3, yield_stress=250e6, hardening=1e9
        )
        assert isinstance(mat, J2PlasticMaterial)
        assert mat.hardening_modulus == 1e9
    
    def test_create_from_dict(self):
        """测试从字典创建"""
        props = {
            'E': 210e9,
            'nu': 0.3,
            'plastic': {
                'yield_stress': 250e6,
                'hardening': 1e9
            }
        }
        mat = MaterialFactory.create('Steel', props)
        assert isinstance(mat, J2PlasticMaterial)
    
    def test_missing_parameters(self):
        """测试缺少参数时的错误"""
        with pytest.raises(ValueError):
            MaterialFactory.create('Bad', {'E': 210e9})


class TestVoigtConversions:
    """测试 Voigt 转换"""
    
    def test_tensor_to_voigt_roundtrip(self):
        """测试张量-Voigt 往返转换"""
        T = np.array([
            [100, 30, 20],
            [30, 80, 15],
            [20, 15, 60]
        ])
        
        v = tensor_to_voigt(T, engineering=True)
        T_back = voigt_to_tensor(v, engineering=True)
        
        assert np.allclose(T, T_back)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
