from dimension_breakout import simple_breakout
from skill_framework import SkillInput
from skill_framework.preview import preview_skill


class TestLegacyBreakout:

    def test_simple_breakout_skill(self):
        '''
        Checks to see if the simple breakout skill runs without errors
        '''

        skill_input: SkillInput = simple_breakout.create_input(arguments={'metrics': ["sold_9le", "menu_placements"], 'breakouts': ["cocktail_family"], 'periods': ["Q1 2024"],
                   'other_filters': [{"dim": "brand_name", "op": "=", "val": ["Papa's Pilar"]}]})
        out = simple_breakout(skill_input)
        preview_skill(simple_breakout, out)

        assert True
