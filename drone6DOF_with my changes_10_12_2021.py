# -*- coding: utf-8 -*-
"""
Created on Thu Aug 19 20:15:53 2021

@author: glick
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import json, codecs
import utm


# Physical Constants
m = 0.1         #kg
Ixx = 0.00062   #kg-m^2
Iyy = 0.00113   #kg-m^2
Izz = 0.9*(Ixx + Iyy) #kg-m^2 (Assume nearly flat object, z=0)
dx = 0.114      #m
dy = 0.0825     #m
g = 9.81  #m/s/s
DTR = 1/57.3; RTD = 57.3


# Simulation time and model parameters
tstep = 0.02            # Sampling time (sec)
simulation_time = 30   # Length of time to run simulation (sec)
t = np.arange(0,simulation_time,tstep)   # time array

# Model size
n_states = 12  # Number of states
n_inputs = 4   # Number of inputs


# Initialize State Conditions
x = np.zeros((n_states,np.size(t)))  # time history of state vectors
# Initial height
x[11,0] = 0.0


# Initialize inputs
u = np.zeros((n_inputs,np.size(t)))  # time history of input vectors
# Initial control inputs
u[:,0] = np.zeros(4)



# Propeller Thrust equations as a function of propeller induced velocity, vi
def thrustEqn(vi, *prop_params):
    
    # Unpack parameters
    R,A,rho,a,b,c,eta,theta0,theta1,U,V,W,Omega = prop_params
    
    # Calculate local airflow velocity at propeller with vi, V'
    Vprime = np.sqrt(U**2 + V**2 + (W - vi)**2)
    
    # Calculate Thrust averaged over one revolution of propeller using vi
    Thrust = 1/4 * rho * a * b * c * R * \
        ( (W - vi) * Omega * R + 2/3 * (Omega * R)**2 * (theta0 + 3/4 * theta1) + \
          (U**2 + V**2) * (theta0 + 1/2 * theta1) )
    
    # Calculate residual for equation: Thrust = mass flow rate * delta Velocity
    residual = eta * 2 * vi * rho * A * Vprime - Thrust
    
    return residual

    
def Fthrust(x, u, dx, dy):
    # Inputs: Current state x[k], Commanded Propeller RPM inputs u[k],
    #         Propeller location distances dx, dy (m)
    # Returns: Thrust vector for 4 propellers (Newtons)
    
    # Propeller Configuration parameters
    
    R = 0.0762   # propeller length/ disk radius (m) 
    A = np.pi * R ** 2
    rho = 1.225  #kg/m^3  at MSL
    a = 5.7      # Lift curve slope used in example in Stevens & Lewis
    b = 2        # number of blades
    c = 0.0274   # mean chord length (m)
    eta = 1      # propeller efficiency
    
    # Manufacturer propeller length x pitch specification:
    p_diameter = 6  #inches
    p_pitch = 3   #inches
    
    theta0 = 2*np.arctan2(p_pitch, (2 * np.pi * 3/4 * p_diameter/2))
    theta1 = -4 / 3 * np.arctan2(p_pitch, 2 * np.pi * 3/4 * p_diameter/2)
    
    
    # Local velocity at propeller from vehicle state information
    ub, vb, wb = x[0], x[1], x[2]
    p, q, r = x[3], x[4], x[5]
    # Transofrm velocity to local propeller location:
    #     [U,V,W] = [ub,vb,wb] + [p,q,r] x [dx,dy,0]
    U = ub - r * dy
    V = vb + r * dx
    W = wb - q * dx + p * dy
    
    # Convert commanded RPM to rad/s
    Omega = 2 * np.pi / 60 * u
    
    #Collect propeller config, state, and input parameters
    prop_params = (R,A,rho,a,b,c,eta,theta0,theta1,U,V,W,Omega)
    
    # Numerically solve for propeller induced velocity, vi
    # using nonlinear root finder, fsolve, and prop_params
    vi0 = 0.1    # initial guess for vi
    vi = fsolve(thrustEqn, vi0, args=prop_params)
    
    # Plug vi back into Thrust equation to solve for T
    Vprime = np.sqrt(U**2 + V**2 + (W - vi)**2)
    Thrust = eta * 2 * vi * rho * A * Vprime
    
    return Thrust

    
# Torque function
def T(F,dx,dy):
    # Returns torque about cg given thrust force and dx,dy distance from cg
    
    #### PLACEHOLDER ####
    return 0

# Nonlinear Dynamics Equations of Motion
def stateDerivative(x,u):
    # Inputs: state vector (x), input vector (u)
    # Returns: time derivative of state vector (xdot)
    
    #  State Vector Reference:
    #idx  0, 1, 2, 3, 4, 5,  6,   7,   8,   9, 10, 11
    #x = [u, v, w, p, q, r, phi, the, psi, xE, yE, hE]
    
    # Store state variables in a readable format
    ub = x[0]
    vb = x[1]
    wb = x[2]
    p = x[3]
    q = x[4]
    r = x[5]
    phi = x[6]
    theta = x[7]
    psi = x[8]
    xE = x[9]
    yE = x[10]
    hE = x[11]
    
    # Calculate forces from propeller inputs (u)
    F1 = Fthrust(x, u[0],  dx,  dy)
    F2 = Fthrust(x, u[1], -dx, -dy)
    F3 = Fthrust(x, u[2],  dx, -dy)
    F4 = Fthrust(x, u[3], -dx,  dy)
    Fz = F1 + F2 + F3 + F4
    L = (F2 + F3) * dy - (F1 + F4) * dy
    M = (F1 + F3) * dx - (F2 + F4) * dx
    N = -T(F1,dx,dy) - T(F2,dx,dy) + T(F3,dx,dy) + T(F4,dx,dy)       #TO COMPLETE, for example: Control and Path Planning of Quadrotor Aerial Vehicles for Search and Rescue,2011
    
    # Pre-calculate trig values
    cphi = np.cos(phi);   sphi = np.sin(phi)
    cthe = np.cos(theta); sthe = np.sin(theta)
    cpsi = np.cos(psi);   spsi = np.sin(psi)
    
    # Calculate the derivative of the state matrix using EOM
    xdot = np.zeros(12)
    
    xdot[0] = -g * sthe + r * vb - q * wb  # = udot
    xdot[1] = g * sphi*cthe - r * ub + p * wb # = vdot
    xdot[2] = 1/m * (-Fz) + g*cphi*cthe + q * ub - p * vb # = wdot
    xdot[3] = 1/Ixx * (L + (Iyy - Izz) * q * r)  # = pdot
    xdot[4] = 1/Iyy * (M + (Izz - Ixx) * p * r)  # = qdot
    xdot[5] = 1/Izz * (N + (Ixx - Iyy) * p * q)  # = rdot
    xdot[6] = p + (q*sphi + r*cphi) * sthe / cthe  # = phidot
    xdot[7] = q * cphi - r * sphi  # = thetadot
    xdot[8] = (q * sphi + r * cphi) / cthe  # = psidot
    
    xdot[9] = cthe*cpsi*ub + (-cphi*spsi + sphi*sthe*cpsi) * vb + \
        (sphi*spsi+cphi*sthe*cpsi) * wb  # = xEdot
        
    xdot[10] = cthe*spsi * ub + (cphi*cpsi+sphi*sthe*spsi) * vb + \
        (-sphi*cpsi+cphi*sthe*spsi) * wb # = yEdot
        
    xdot[11] = -1*(-sthe * ub + sphi*cthe * vb + cphi*cthe * wb) # = hEdot
    
    return xdot

def rotationMatrix (x):
    
    phi = x[6]
    theta = x[7]
    psi = x[8]
    
    # Pre-calculate trig values
    cphi = np.cos(phi);   sphi = np.sin(phi)
    cthe = np.cos(theta); sthe = np.sin(theta)
    cpsi = np.cos(psi);   spsi = np.sin(psi)
    
    #  Direct Cosine Matrix (Siouris pp.22) - EARTH TO BODY
    RInertialToBody = np.array(((cpsi*cthe, cthe*spsi, -sthe), (sphi*sthe*cpsi-cphi*spsi, sphi*sthe*spsi+cphi*cpsi, sphi*cthe),(cphi*sthe*cpsi+sphi*spsi, cphi*sthe*spsi-sphi*cpsi, cthe*cphi)))

    #  EULER TO QUATERNIONS - NEED TO CHECK

    q = np.array (((0.5*(cphi*cthe*cpsi+sphi*sthe*spsi)),(0.5*(-cphi*sthe*spsi+cthe*cpsi*sphi)),(0.5*(cphi*cpsi*sthe+sphi*cpsi*spsi)),(0.5*(cphi*cthe*spsi-sphi*cpsi*sthe))))
    
    return RInertialToBody


def controlInputs(x, t):
    # Inputs: Current state x[k], time t
    # Returns: Control inputs u[k]
    
    #### Placeholder Function ####
    
    # Trim RPM for all 4 propellers to provide thrust for a level hover
    trim = 3200
    
    pitch_cmd = 0
    roll_cmd = 0
    climb_cmd = 0
    yaw_cmd = 0
    
    # Example open loop control inputs to test dynamics:
    #  Climb
    if t < 11.0:
        climb_cmd = 500
    
    #  Pitch Forward
    if t > 8.0:
        pitch_cmd = -10
    if t > 9.0:
        pitch_cmd = 10
    if t > 10.0:
        pitch_cmd = 0
    
    #  Pitch Backward
    if t > 12.0:
        pitch_cmd = 15
    if t > 13.0:
        pitch_cmd = -15
    if t > 14.0:
        pitch_cmd = 0
    
    #  Increase lift
    if t > 16.0:
        climb_cmd = 150
        
    
    # RPM command based on pitch, roll, climb, yaw commands
    u = np.zeros(4)
    u[0] = trim + ( pitch_cmd + roll_cmd + climb_cmd - yaw_cmd) / 4
    u[1] = trim + (-pitch_cmd - roll_cmd + climb_cmd - yaw_cmd) / 4
    u[2] = trim + ( pitch_cmd - roll_cmd + climb_cmd + yaw_cmd) / 4
    u[3] = trim + (-pitch_cmd + roll_cmd + climb_cmd + yaw_cmd) / 4
    
    
    return u

# 4th Order Runge Kutta Calculation
def RK4(x,u,dt):
    # Inputs: x[k], u[k], dt (time step, seconds)
    # Returns: x[k+1]
    
    # Calculate slope estimates
    K1 = stateDerivative(x, u)
    K2 = stateDerivative(x + K1 * dt / 2, u)
    K3 = stateDerivative(x + K2 * dt / 2, u)
    K4 = stateDerivative(x + K3 * dt, u)
    
    # Calculate x[k+1] estimate using combination of slope estimates
    x_next = x + 1/6 * (K1 + 2*K2 + 2*K3 + K4) * dt
    
    return x_next


def IMU_model(x,u):
    # Inputs: real dynamic
    # Returns: IMU output
    xdot = stateDerivative(x, u)   #Calculating acceleration
    
    # GYRO Output:
    gyro_mu, gyro_sigma = 0, 0.1   # TO COMPLETE: UNITS and MPU6000 values
    gyro_bias = 0
    gyro_noise = gyro_bias +  np.random.normal(gyro_mu, gyro_sigma, 3)
    gyro_output = x[3:6] + gyro_noise + gyro_bias
    
    
    # Accelerometer Output:
    acc_mu, acc_sigma = 0, 0.1   # TO COMPLETE: UNITS and MPU6000 values
    acc_bias = 0
    acc_noise = acc_bias +  np.random.normal(acc_mu, acc_sigma, 3)
      
    RinertialToBody = rotationMatrix (x)
    g_vectorInertial = np.array(0,0,9.8)                   #TO CHECK: Z positive = DOWN according R
    
    acc_output = xdot[9:12] - RinertialToBody*g_vectorInertial + acc_noise + acc_bias       # TO COMPLETE: accelerometer output = R(a-g)+noise   
    
    IMU_output = np.concatenate((gyro_output,acc_output), axis=None)
    
    # NEED TO COMPLETE: IMU HIGH rates outputs 

    return IMU_output

def Magnetometer_model(x):
    
    #psi = x[8]                     psi - azimuth angle

    
    RinertialToBody = rotationMatrix (x)
    

    magnetometer_Output = RinertialToBody*[0,0,1] * 14    #TO COMPLETE: ISRAEL MAGNITUTE FIELD, UNITS: microF
        
    
    return magnetometer_Output
    
    
    
    return 0 


def Barometer_model(x,m):
    
    heightOfLaunchAboveSeaLevel = 0;
    
    h = heightOfLaunchAboveSeaLevel + x[11]  #heightAboveSeaLevel
    
    K = 1.38 * np.power(10, -23)    # Boltzman constant
    
    T = 298                         # Kelvin
    
    p0 = 101325                     # [pa]
    
    g = 9.8
    
    ph = p0*np.exp((-1)*m*g*h/(K*T)) #[pa]
    
    return ph
        

def gps_model(x):
    
    launchNorthing = 3539643      #Mitvah 24, 3 Bet
    
    launchEasting = 664026
    
    zone = 36
    
    launchAltitude = 0            #Above elipsoid
    
    lat,lon = utm.to_latlon(launchEasting,launchNorthing,zone,zone_letter='N',northern=None, strict=True)    
    
    gps_Output = np.array(lat,lon,launchAltitude+x[11],launchNorthing+x[9],launchEasting+x[10]+launchAltitude+x[11])
    
    return gps_Output


# March through time array and numerically solve for vehicle states

for k in range(0, np.size(t) - 1): 
        
    # Determine control inputs based on current state
    u[:,k] = controlInputs(x[:,k], t[k])
    
    # Predict state after one time step
    x[:,k+1] = RK4(x[:,k], u[:,k], tstep)
    
    #IMU_output: [gyro,accelerometer]
    IMU_output = IMU_model(x[:,k], u[:,k])
    
    #Magnetometer_output: 
    magnetometer_Output = Magnetometer_model(x[:,k])
    
    #Barometer_output: 
    Barometer_Output = Barometer_model(x[:,k],m)
    
    #gps_output: 
    gps_Output = gps_model(x[:,k])
    





# LOG

#Store time, input, and state data to a json file for visualization
#log_filename = "visualizer/sim_log.json"
#with open(log_filename, "w") as logfile:
#    logfile.write("var sim_data = ")
#json.dump([t.tolist(), u.tolist(),x.tolist()], \
#          codecs.open(log_filename, 'a', encoding='utf-8'), \
#          separators=(',', ':'), indent=4)



# PLOT
plt.figure(1, figsize=(8,8))
plt.subplot(311)
plt.plot(t,x[11,:],'b',label='h')
plt.ylabel('h (m)')
#plt.xlabel('Time (sec)')
#plt.legend(loc='best')
plt.title('Time History of Height, X Position, and Pitch')

plt.subplot(312)
plt.plot(t,x[9,:],'b',label='x')
plt.ylabel('x (m)')
#plt.xlabel('Time (sec)')

plt.subplot(313)
plt.plot(t,x[7,:]*RTD,'b',label='theta')
plt.ylabel('Theta (deg)')
plt.xlabel('Time (sec)')

plt.figure(2, figsize=(8,8))
ax = plt.subplot(1,1,1)
plt.plot(x[9,0:-1:20],x[11,0:-1:20],'bo-',label='y')
plt.text(x[9,0] + 0.1, x[11,0],'START')
plt.text(x[9,-1], x[11,-1],'END')
plt.ylabel('h [m]'); plt.xlabel('x [m]')
ax.axis('equal')
#plt.legend(loc='best')
plt.title('Vertical Profile')

plt.figure(3, figsize=(8,4))
plt.plot(t[0:-1],u[0,0:-1],'b',label='T1')
plt.plot(t[0:-1],u[1,0:-1],'g',label='T2')
plt.plot(t[0:-1],u[2,0:-1],'r',label='T3')
plt.plot(t[0:-1],u[3,0:-1],'y',label='T4')
plt.xlabel('Time (sec)')
plt.ylabel('Propeller RPM')
plt.legend(loc='best')
plt.title('Time History of Control Inputs')

plt.show()

# Plot Thrust as a function of RPM for various vertical velocity conditions
RPM = np.linspace(1000,6000,200)
vertvel = np.array([0,0,1] + 9*[0])
Thrust_m2vel = np.array([Fthrust(2*vertvel,rpmIn,dx,dy) for rpmIn in RPM])
Thrust_m1vel = np.array([Fthrust(1*vertvel,rpmIn,dx,dy) for rpmIn in RPM])
Thrust_0vel  = np.array([Fthrust(0*vertvel,rpmIn,dx,dy) for rpmIn in RPM])
Thrust_p1vel = np.array([Fthrust(-1*vertvel,rpmIn,dx,dy) for rpmIn in RPM])
Thrust_p2vel = np.array([Fthrust(-2*vertvel,rpmIn,dx,dy) for rpmIn in RPM])
fig = plt.figure(figsize=(8,8))
plt.plot(RPM, 4 * Thrust_m2vel / (m*g) )
plt.plot(RPM, 4 * Thrust_m1vel / (m*g) )
plt.plot(RPM, 4 * Thrust_0vel / (m*g) )
plt.plot(RPM, 4 * Thrust_p1vel / (m*g) )
plt.plot(RPM, 4 * Thrust_p2vel / (m*g) )
plt.plot(RPM, np.ones(np.size(RPM)), 'k--')
plt.legend(('Airspeed = -2 m/s','Airpseed = -1 m/s','Airspeed =  0 m/s', \
            'Airpseed =  1 m/s','Airspeed =  2 m/s'), loc='upper left')
plt.xlabel('Propeller RPM (x4)')
plt.ylabel('Thrust (g)')
plt.title('Quadcopter Thrust for different Vertical Airspeeds')
plt.show()