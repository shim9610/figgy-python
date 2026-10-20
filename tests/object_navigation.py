"""Real object-tree input shared by browser integration scenarios."""
import json


def ensure_native_control_visible(info, xdo, pump, wid, name):
    """Scroll a form with real X11 wheel input before clicking a clipped row."""
    if name.lower() != name or name in {'advanced', 'close_properties', 'properties', 'properties_header', 'properties_viewport', 'copy', 'fit', 'select_mode', 'layout_mode', 'visibility_menu', 'draw_style_menu', 'navigation_help'} or name.startswith(('tree', 'object_', 'style_', 'save', 'draw', 'choose:', 'choice_', 'switch_chart')):
        return
    for _ in range(35):
        state = info()
        rect = state['controls'].get(name)
        view = state['controls'].get('properties_viewport')
        if not rect or not view or rect[0] < view[0]-2 or rect[0] > view[0]+view[2]:
            return
        if rect[1] >= view[1]-1 and rect[1]+rect[3] <= view[1]+view[3]+1:
            return
        xdo('mousemove', '--window', wid, round(view[0]+view[2]/2), round(view[1]+view[3]/2))
        xdo('click', 4 if rect[1] < view[1]-1 else 5)
        pump()
    raise AssertionError(f'Cannot scroll to {name}: {rect}, viewport={view}')


class ObjectNavigator:
    def __init__(self, page):
        self.page = page

    def choose(self, target):
        search = self.page.locator('[data-object-search]')
        search.fill(target.split(':')[-1])
        row = self.page.locator(f'[role=treeitem][data-object={json.dumps(target)}]')
        row.click()
        search.fill('')

    def panel(self, panel_id):
        search = self.page.locator('[data-object-search]')
        search.fill(panel_id)
        self.page.locator(f'[role=treeitem][data-node={json.dumps("panel/"+panel_id)}]').click()
        search.fill('')

    def selected(self):
        return self.page.locator('.figgy-editor [data-context]').get_attribute('data-target')
