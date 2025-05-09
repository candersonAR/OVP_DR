
from ar_analytics import BreakoutAnalysis
from overproof_utilities import OverproofSharedFn

class OverproofBreakoutAnalysis(BreakoutAnalysis):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = OverproofSharedFn()
