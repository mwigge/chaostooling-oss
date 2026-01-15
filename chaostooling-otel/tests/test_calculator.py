"""
Tests for ChaoSOTEL calculator module.

Tests risk level and complexity score calculations.
"""

from chaosotel.calculator import (calculate_complexity_score,
                                  calculate_risk_level)


class TestRiskLevelCalculation:
    """Test risk level calculation."""

    def test_low_risk(self):
        """Test low-risk scenario."""
        experiment = {
            "severity": "low",
            "blast_radius": 1,
            "can_rollback": True,
            "is_production": False,
        }
        result = calculate_risk_level(experiment)

        assert 1 <= result["level"] <= 4
        assert result["level_name"] in ["Low", "Medium", "High", "Critical"]

    def test_medium_risk(self):
        """Test medium-risk scenario."""
        experiment = {
            "severity": "medium",
            "blast_radius": 5,
            "can_rollback": True,
            "is_production": False,
        }
        result = calculate_risk_level(experiment)

        assert 1 <= result["level"] <= 4
        assert result["level_name"] in ["Low", "Medium", "High", "Critical"]

    def test_high_risk(self):
        """Test high-risk scenario."""
        experiment = {
            "severity": "high",
            "blast_radius": 50,
            "can_rollback": False,
            "is_production": True,
        }
        result = calculate_risk_level(experiment)

        assert 1 <= result["level"] <= 4
        assert result["level_name"] in ["Low", "Medium", "High", "Critical"]

    def test_critical_risk(self):
        """Test critical-risk scenario."""
        experiment = {
            "severity": "critical",
            "blast_radius": 100,
            "can_rollback": False,
            "is_production": True,
        }
        result = calculate_risk_level(experiment)

        assert 1 <= result["level"] <= 4
        assert result["level_name"] in ["Low", "Medium", "High", "Critical"]

    def test_blast_radius_impact(self):
        """Test blast radius impact on risk."""
        low = calculate_risk_level(
            {
                "severity": "medium",
                "blast_radius": 1,
                "can_rollback": True,
                "is_production": False,
            }
        )

        high = calculate_risk_level(
            {
                "severity": "medium",
                "blast_radius": 100,
                "can_rollback": True,
                "is_production": False,
            }
        )

        # Higher blast radius should have higher or equal risk
        assert high["level"] >= low["level"]

    def test_rollback_impact(self):
        """Test rollback capability impact."""
        with_rollback = calculate_risk_level(
            {
                "severity": "high",
                "blast_radius": 50,
                "can_rollback": True,
                "is_production": True,
            }
        )

        without_rollback = calculate_risk_level(
            {
                "severity": "high",
                "blast_radius": 50,
                "can_rollback": False,
                "is_production": True,
            }
        )

        # Without rollback should have higher or equal risk
        assert without_rollback["level"] >= with_rollback["level"]

    def test_production_impact(self):
        """Test production environment impact."""
        non_prod = calculate_risk_level(
            {
                "severity": "high",
                "blast_radius": 50,
                "can_rollback": False,
                "is_production": False,
            }
        )

        prod = calculate_risk_level(
            {
                "severity": "high",
                "blast_radius": 50,
                "can_rollback": False,
                "is_production": True,
            }
        )

        # Production should have higher or equal risk
        assert prod["level"] >= non_prod["level"]

    def test_risk_factors_present(self):
        """Test presence of risk factors."""
        result = calculate_risk_level(
            {
                "severity": "high",
                "blast_radius": 50,
                "can_rollback": False,
                "is_production": True,
            }
        )

        assert "level" in result
        assert "level_name" in result
        assert "factors" in result
        assert len(result["factors"]) > 0

    def test_default_values(self):
        """Test default values."""
        result = calculate_risk_level({})

        assert 1 <= result["level"] <= 4
        assert result["level_name"] is not None
        assert "score" in result


class TestComplexityScoreCalculation:
    """Test complexity score calculation."""

    def test_simple_complexity(self):
        """Test simple complexity."""
        experiment = {
            "num_steps": 1,
            "estimated_duration_minutes": 5,
            "required_skills": "basic",
        }
        result = calculate_complexity_score(experiment)

        assert result["difficulty"] in [
            "Simple",
            "Intermediate",
            "Advanced",
            "Expert",
            "Master",
        ]
        assert result["score"] >= 0

    def test_intermediate_complexity(self):
        """Test intermediate complexity."""
        experiment = {
            "num_steps": 5,
            "estimated_duration_minutes": 30,
            "required_skills": "intermediate",
        }
        result = calculate_complexity_score(experiment)

        assert result["difficulty"] in [
            "Simple",
            "Intermediate",
            "Advanced",
            "Expert",
            "Master",
        ]
        assert result["score"] >= 0

    def test_advanced_complexity(self):
        """Test advanced complexity."""
        experiment = {
            "num_steps": 10,
            "estimated_duration_minutes": 120,
            "required_skills": "advanced",
        }
        result = calculate_complexity_score(experiment)

        assert result["difficulty"] in [
            "Simple",
            "Intermediate",
            "Advanced",
            "Expert",
            "Master",
        ]
        assert result["score"] >= 0

    def test_expert_complexity(self):
        """Test expert complexity."""
        experiment = {
            "num_steps": 15,
            "estimated_duration_minutes": 240,
            "required_skills": "expert",
        }
        result = calculate_complexity_score(experiment)

        assert result["difficulty"] in [
            "Simple",
            "Intermediate",
            "Advanced",
            "Expert",
            "Master",
        ]
        assert result["score"] >= 0

    def test_master_complexity(self):
        """Test master complexity."""
        experiment = {
            "num_steps": 20,
            "estimated_duration_minutes": 480,
            "required_skills": "master",
        }
        result = calculate_complexity_score(experiment)

        assert result["difficulty"] in [
            "Simple",
            "Intermediate",
            "Advanced",
            "Expert",
            "Master",
        ]
        assert result["score"] >= 0

    def test_steps_impact(self):
        """Test steps impact on complexity."""
        few_steps = calculate_complexity_score({"num_steps": 1})
        many_steps = calculate_complexity_score({"num_steps": 20})

        # More steps should have higher or equal score
        assert many_steps["score"] >= few_steps["score"]

    def test_duration_impact(self):
        """Test duration impact on complexity."""
        short = calculate_complexity_score({"estimated_duration_minutes": 5})
        long = calculate_complexity_score({"estimated_duration_minutes": 480})

        # Longer duration should have higher or equal score
        assert long["score"] >= short["score"]

    def test_complexity_factors_present(self):
        """Test presence of complexity factors."""
        result = calculate_complexity_score(
            {
                "num_steps": 10,
                "estimated_duration_minutes": 120,
                "required_skills": "advanced",
            }
        )

        assert "difficulty" in result
        assert "score" in result
        assert "factors" in result

    def test_default_complexity(self):
        """Test default complexity values."""
        result = calculate_complexity_score({})

        assert result["difficulty"] is not None
        assert result["score"] >= 0


class TestMetricsExport:
    """Test metrics export."""

    def test_export_with_defaults(self, initialized_chaosotel):
        """Test exporting metrics with defaults."""
        result = calculate_risk_level({})

        assert 1 <= result["level"] <= 4
        assert "level_name" in result

    def test_export_high_risk_experiment(self, initialized_chaosotel):
        """Test exporting high-risk experiment metrics."""
        result = calculate_risk_level(
            {
                "severity": "high",
                "blast_radius": 50,
                "can_rollback": False,
                "is_production": True,
            }
        )

        assert 1 <= result["level"] <= 4

    def test_export_complex_experiment(self, initialized_chaosotel):
        """Test exporting complex experiment metrics."""
        result = calculate_complexity_score(
            {
                "num_steps": 15,
                "estimated_duration_minutes": 240,
                "required_skills": "expert",
            }
        )

        assert result["difficulty"] in [
            "Simple",
            "Intermediate",
            "Advanced",
            "Expert",
            "Master",
        ]

    def test_export_failed_experiment(self, initialized_chaosotel):
        """Test exporting failed experiment metrics."""
        result = calculate_risk_level(
            {
                "severity": "critical",
                "blast_radius": 100,
                "can_rollback": False,
                "is_production": True,
            }
        )

        assert 1 <= result["level"] <= 4


class TestEdgeCases:
    """Test edge cases."""

    def test_risk_with_invalid_severity(self):
        """Test risk with invalid severity."""
        result = calculate_risk_level({"severity": "unknown"})

        assert 1 <= result["level"] <= 4

    def test_complexity_with_zero_values(self):
        """Test complexity with zero values."""
        result = calculate_complexity_score(
            {"num_steps": 0, "estimated_duration_minutes": 0}
        )

        assert result["difficulty"] is not None
        assert result["score"] >= 0

    def test_export_with_missing_fields(self, initialized_chaosotel):
        """Test export with missing fields."""
        result = calculate_risk_level({})

        assert result is not None
        assert "level" in result
