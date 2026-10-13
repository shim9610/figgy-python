import numpy as np
import figgy.pyplot as plt

x = np.linspace(0, 20, 100_000)
fig, ax = plt.subplots()
ax.plot(x, np.sin(x), label="signal", id="signal")
ax.set_title("100,000 samples")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Amplitude")
ax.legend()
fig.savefig("signal.png")
plt.show()
