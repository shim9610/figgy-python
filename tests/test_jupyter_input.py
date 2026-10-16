"""Input preconditions must not depend on GPU presentation scheduling."""
import os
import shutil

import pytest

from jupyter_harness import button_point_without_frames


@pytest.mark.skipif(os.environ.get('FIGGY_TEST_JUPYTER') != '1', reason='requires Chromium')
def test_button_input_checks_geometry_without_animation_frames():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
            executable_path=os.environ.get('BROWSER_EXECUTABLE_PATH') or shutil.which('chromium'),
            args=['--no-sandbox', '--disable-gpu'])
        try:
            page = browser.new_page(viewport={'width': 500, 'height': 300})
            page.set_default_timeout(2000)
            cdp = page.context.new_cdp_session(page)
            worlds = []
            cdp.on('Runtime.executionContextCreated', lambda event: worlds.append(event['context']))
            cdp.send('Runtime.enable')
            page.goto('about:blank')
            page.set_content('''<style>
                button {position:absolute;left:100px;top:100px;width:100px;height:40px;border-radius:5px;visibility:hidden}
                #cover {position:absolute;left:0;top:0;width:500px;height:300px;background:white;z-index:2}
                </style><button disabled>Style</button><div id="cover"></div>''')
            # Freeze both the page's RAF and Playwright's isolated-world RAF.
            # A future Locator.click(trial=True) or default wait_for_function
            # in the helper will deterministically time out here.
            for world in worlds:
                try:
                    cdp.send('Runtime.evaluate', {'contextId': world['id'],
                        'expression': 'window.requestAnimationFrame=()=>0'})
                except Exception as exc:
                    if 'Cannot find context' not in str(exc):
                        raise
            page.evaluate('''()=>{
                const button=document.querySelector('button');
                window.clicks=[];
                button.addEventListener('click',e=>window.clicks.push({trusted:e.isTrusted,uncovered:!document.querySelector('#cover')}));
                setTimeout(()=>{button.disabled=false;button.style.visibility='visible';},100);
                setTimeout(()=>document.querySelector('#cover').remove(),300);
            }''')
            x, y = button_point_without_frames(page, 'button')
            assert page.locator('#cover').count() == 0
            assert page.locator('button').is_visible() and page.locator('button').is_enabled()
            assert page.evaluate('([x,y])=>document.elementFromPoint(x,y)===document.querySelector("button")', [x,y])
            page.mouse.click(x,y)
            assert page.evaluate('window.clicks') == [{'trusted': True, 'uncovered': True}]
        finally:
            browser.close()
