"""VisionMaster-aligned workbench widgets for SIEANS Vision."""
from .switch import OrangeSwitch
from .filmstrip import FilmstripBar, CompareThumbStrip
from .minimap import MiniMap
from .op_rail import OperatorRail
from .status_chrome import WorkbenchStatusBar
from .flow_tabs import FlowTabBar
from .all_flows import AllFlowsPanel

__all__ = [
    'OrangeSwitch', 'FilmstripBar', 'CompareThumbStrip', 'MiniMap', 'OperatorRail', 'WorkbenchStatusBar',
    'FlowTabBar', 'AllFlowsPanel',
]
