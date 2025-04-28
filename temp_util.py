import numpy as np
from typing import List, Any, Optional

def sparkline(original_data: List[Any]) -> List[Optional[float]]:
    """Returns list of values for sparkline"""
    data = []
    for point in original_data:

        try:
            if not point:
                point = None
            elif np.isnan(point):
                point = None
            else:
                point = round(float(point), 4)
        except:
            point = None
        
        data.append(point)

    return data
