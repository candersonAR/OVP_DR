
from overproof_utilities import OverproofSharedFn


class TestOverproofUtilities:

    def test_x_formatting(self):
        helper = OverproofSharedFn()
        assert helper.get_formatted_num(0.23, ",.2x") == "0.23x"
        assert helper.get_formatted_num(1.23, ",.2x") == "1.23x"
        assert helper.get_formatted_num(1234567890.1213213, ",.2x") == "1234567890.12x"
        assert helper.get_formatted_num(1234567890.1213213, ",.3x") == "1234567890.121x"
        