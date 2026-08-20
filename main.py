"""
Main entry point for the Photo Viewer application
"""
import sys
from PyQt6.QtWidgets import QApplication
from viewer import PhotoViewer

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = PhotoViewer()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()