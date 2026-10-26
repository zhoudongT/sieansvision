import argparse
import sys
from pathlib import Path
from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication,QMessageBox


def main():
    parser=argparse.ArgumentParser(description='SIEANS Vision native desktop')
    parser.add_argument('--root',type=Path)
    parser.add_argument('--data',type=Path)
    args=parser.parse_args()
    app=QApplication(sys.argv[:1]);app.setOrganizationName('SIEANS');app.setApplicationName('SIEANS Vision Native')
    root=args.root
    if root is None:
        marker=Path(sys.executable).parent/'runtime-root.txt'
        root=Path(marker.read_text(encoding='utf-8').strip()) if getattr(sys,'frozen',False) and marker.exists() else Path(__file__).resolve().parent.parent
    if not (root/'lib/runtime.cjs').exists():
        QMessageBox.critical(None,'无法找到算法运行环境','请使用附带运行环境的目录，或通过 --root 指定现有 SIEANS 工程目录。');return 2
    data=args.data or Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))/'native-data'
    from desktop.mainwindow import MainWindow
    window=MainWindow(root,data);window.show()
    return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
