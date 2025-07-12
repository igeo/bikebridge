import cv2
import numpy as np

def nothing(_): pass
cv2.namedWindow("mask")

# six sliders → Hlow, Slow, Vlow, Hhigh, Shigh, Vhigh
for name, init in zip(("Hlow","Slow","Vlow","Hhigh","Shigh","Vhigh"),
                      (70,   80,    140,  110,   255,   255)):
    cv2.createTrackbar(name, "mask", init, 255, nothing)

frame = cv2.imread("test_image_1.jpg")            # one good snapshot
# resize for faster processing
frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
hsv   = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

while True:
    hL = cv2.getTrackbarPos("Hlow","mask")
    sL = cv2.getTrackbarPos("Slow","mask")
    vL = cv2.getTrackbarPos("Vlow","mask")
    hH = cv2.getTrackbarPos("Hhigh","mask")
    sH = cv2.getTrackbarPos("Shigh","mask")
    vH = cv2.getTrackbarPos("Vhigh","mask")
    
    mask = cv2.inRange(hsv, (hL,sL,vL), (hH,sH,vH))
    cv2.imshow("mask", mask)
    if cv2.waitKey(1) == 27:        # press <Esc> when you’re happy
        print("LOW :", hL, sL, vL)
        print("HIGH:", hH, sH, vH)
        break
