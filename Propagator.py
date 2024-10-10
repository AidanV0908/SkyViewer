import Earth;
import numpy as np;

# Turn on/off J2
IS_J2 = True

# Propogate an object's orbit
def propagator(t, rv):
    # Instantiate a version of the Earth
    earth = Earth.earth()
    x, y, z, vx, vy, vz = rv
    r = np.sqrt(np.pow(rv[0],2) + np.pow(rv[1],2) + np.pow(rv[2],2))
    # Latitude
    lat = np.arcsin(z / r)
    fx = vx
    fy = vy
    fz = vz
    fvx = -earth.Mu() * (rv[0] / np.pow(r, 3))
    fvy = -earth.Mu() * (rv[1] / np.pow(r, 3))
    fvz = -earth.Mu() * (rv[2] / np.pow(r, 3))
    if (IS_J2):
        fvx += (1/2) * (earth.Mu() * earth.J2() * np.pow(earth.Radius(lat), 2) * ((15*x*np.pow(z,2) / np.pow(r, 7)) - (3*x / (np.pow(r, 5)))))
        fvy += (1/2) * (earth.Mu() * earth.J2() * np.pow(earth.Radius(lat), 2) * ((15*y*np.pow(z,2) / np.pow(r, 7)) - (3*y / (np.pow(r, 5)))))
        fvz += (1/2) * (earth.Mu() * earth.J2() * np.pow(earth.Radius(lat), 2) * ((15*np.pow(z,3) / np.pow(r, 7)) - (9*z / (np.pow(r, 5)))))
    return fx, fy, fz, fvx, fvy, fvz