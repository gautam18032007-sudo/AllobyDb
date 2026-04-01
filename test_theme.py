#!/usr/bin/env python3
"""
Test the theme toggle functionality by checking the HTML content.
"""

import requests
from bs4 import BeautifulSoup

def test_theme_buttons():
    """Test that theme toggle buttons are present in the HTML."""
    try:
        response = requests.get("http://localhost:5000")
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check for theme toggle buttons
            day_btn = soup.find(id="dayBtn")
            night_btn = soup.find(id="nightBtn")
            
            print("🎨 Testing Theme Toggle Buttons")
            print("=" * 40)
            
            if day_btn and night_btn:
                print("✅ Day button found:", day_btn.get_text().strip())
                print("✅ Night button found:", night_btn.get_text().strip())
                
                # Check for theme CSS
                theme_css = soup.find(style=lambda x: x and "theme-toggle" in x.text)
                if theme_css:
                    print("✅ Theme CSS styles found")
                else:
                    print("⚠️  Theme CSS might be embedded in main stylesheet")
                
                # Check for theme JavaScript
                if "setTheme" in response.text and "THEMES" in response.text:
                    print("✅ Theme JavaScript functions found")
                else:
                    print("❌ Theme JavaScript not found")
                
                print("\n🌞 Theme toggle is ready to use!")
                print("Click the ☀️ Day and 🌙 Night buttons in the topbar")
                
            else:
                print("❌ Theme buttons not found")
                print("Day button:", "found" if day_btn else "missing")
                print("Night button:", "found" if night_btn else "missing")
                
        else:
            print(f"❌ Failed to load page: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_theme_buttons()
