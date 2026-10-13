# %%
import numpy as np
import figgy

# %%
x = np.linspace(0, 20, 1_000_000)
fig, ax = figgy.subplots(backend="webgpu")
ax.plot(x, np.sin(x), id="signal", label="signal")
ax.set_title("Edit this plot, then copy Python settings")
ax.legend()
display(fig.widget())

# %%
# Paste the editor's Copy Python output here to replay the settings.
await fig.sync()
await fig.savefig_async("edited.png", dpi=240)
