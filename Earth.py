import numpy as np;

# Constants
G = 6.6743*pow(10, -20)

class earth:
    RADIUS_EQ = 6378.137
    FF = 1/298.257223563
    MASS = 5.972*pow(10, 24)
    J2_val = 0.001082635
    r_pol = 6357

    def Mu(self):
        return G * self.MASS

    def Radius(self, geodetic_lat):
        e_sqr = 2*self.FF - np.pow(self.FF, 2)
        return self.RADIUS_EQ / np.sqrt(1 - e_sqr*np.pow(np.sin(geodetic_lat * (180 / np.pi)), 2))
    
    def J2(self):
        return self.J2_val
    
    def Radius_Eq(self):
        return self.RADIUS_EQ
    
    def ecef_to_geodetic(self, x, y, z):
        # Longitude calculation
        lon = np.arctan2(y, x) * (180 / np.pi)

        # Iterative calculation of latitude
        e2 = 1 - (np.power((self.RADIUS_EQ * (1-self.FF)), 2) / np.power(self.RADIUS_EQ, 2))  # square of eccentricity
        p = np.sqrt(np.power(x, 2) + np.power(y, 2))  # distance from z-axis

        lat = np.arctan2(z, p * (1 - e2))  # initial latitude guess
        for _ in range(5):  # iterate to improve accuracy
            N = self.RADIUS_EQ / np.sqrt(1 - e2 * np.power(np.sin(lat), 2))
            # alt = p / np.cos(lat) - N
            lat = np.arctan2(z + e2 * N * np.sin(lat), p)

        # Convert latitude to degrees
        lat = lat * (180 / np.pi)

        return lat, lon
