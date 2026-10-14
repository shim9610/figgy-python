# Apply to the existing fig with the same plotted series.
ax = fig.axes[0]
fig.configure(reset=True)
ax.set_title('Response / Run 01', fontsize=18.0)
ax.set_xlabel('Time (s)', fontsize=11.000000400000001)
ax.set_ylabel('Amplitude', fontsize=11.000000400000001, offset=(0.0, -8.0))
ax.set_xlim(5.933434131454735, 19.339835052167516)
ax.set_xscale('linear')
ax.set_ylim(0.042355634297198574, 2.2119921299538503)
ax.set_yscale('linear')
ax.grid(True)
fig.update('measured', color=(0.14117648, 0.40392157, 0.6784314, 1.0), linewidth=1.2, linestyle='-', label='Measured response')
fig.update('model', color=(0.8980392, 0.5372549, 0.23921569, 1.0), linewidth=1.39999998, linestyle='--', label='Model prediction')
fig.update('baseline', color=(0.2901961, 0.56078434, 0.4627451, 1.0), linewidth=0.99999996, linestyle='-', label='Reference baseline')

# Preserve advanced series styling.
fig.configure(
    series={'measured': {'label': {'color': {'r': 0.0, 'g': 0.0, 'b': 0.0, 'a': 1.0},
                            'font_size': 14.0,
                            'font': ''}},
     'model': {'label': {'color': {'r': 0.0, 'g': 0.0, 'b': 0.0, 'a': 1.0},
                         'font_size': 14.0,
                         'font': ''}},
     'baseline': {'label': {'color': {'r': 0.0, 'g': 0.0, 'b': 0.0, 'a': 1.0},
                            'font_size': 14.0,
                            'font': ''}}},
)
ax.legend(visible=True)

# Preserve advanced layout.
fig.configure(
    config={'top_x': {'major_spacing': 5.0},
     'bottom_x': {'major_spacing': 5.0},
     'left_y': {'major_spacing': 0.5, 'out_margin': 145.0},
     'right_y': {'major_spacing': 0.5},
     'legend': {'content': {'font_size': 18.333334}, 'offset_x': -538.0, 'offset_y': 10.0},
     'chart_area': {'x': 0, 'y': 0, 'width': 960, 'height': 600}},
)
