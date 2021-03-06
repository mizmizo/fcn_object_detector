#!/usr/bin/env python

###########################################################################
## Copyright (C) 2017 by Krishneel Chaudhary @ JSK Lab,
## The University of Tokyo, Japan
###########################################################################

import sys
import math
import random
import numpy as np
import cv2 as cv

import imgaug.imgaug as ia
import imgaug.imgaug
import imgaug.imgaug.augmenters as iaa


"""
Class for computing intersection over union(IOU)
"""
class JaccardCoeff:

    def iou(self, a, b):
        i = self.__intersection(a, b)
        if i == 0:
            return 0
        aub = self.__area(self.__union(a, b))
        anb = self.__area(i)
        area_ratio = self.__area(a)/self.__area(b)        
        score = anb/aub
        score /= area_ratio
        return score
        
    def __intersection(self, a, b):
        x = max(a[0], b[0])
        y = max(a[1], b[1])
        w = min(a[0]+a[2], b[0]+b[2]) - x
        h = min(a[1]+a[3], b[1]+b[3]) - y
        if w < 0 or h < 0:
            return 0
        else:
            return (x, y, w, h)
        
    def __union(self, a, b):
        x = min(a[0], b[0])
        y = min(a[1], b[1])
        w = max(a[0]+a[2], b[0]+b[2]) - x
        h = max(a[1]+a[3], b[1]+b[3]) - y
        return (x, y, w, h)

    def __area(self, rect):
        return np.float32(rect[2] * rect[3])


class ArgumentationEngine(object):
    def __init__(self, im_width, im_height, stride, num_classes):
        self.__net_size_x = im_width
        self.__net_size_y = im_height
        self.__stride = stride
        self.__num_classes = num_classes
        
        self.__jc = JaccardCoeff()
        self.FORE_PROB_ = np.float32(1.0)
        self.FLT_EPSILON_ = 0.5 #sys.float_info.epsilon

    def bounding_box_parameterized_labels(self, img, rects, labels):
        boxes = self.grid_region(img, self.__stride)
        
        channel_stride = 4 
        channels = int(self.__num_classes * channel_stride)
        
        foreground_labels = np.zeros((self.__num_classes, boxes.shape[0], boxes.shape[1])) # 1
        boxes_labels = np.zeros((channels, boxes.shape[0], boxes.shape[1])) # 4
        size_labels = np.zeros((channels, boxes.shape[0], boxes.shape[1])) # 2
        obj_labels = np.zeros((channels, boxes.shape[0], boxes.shape[1])) # 1
        coverage_label = np.zeros((channels, boxes.shape[0], boxes.shape[1])) # 1

        for rect, label in zip(rects, labels):
            k = int(label * channel_stride)
            region_labels = self.generate_box_labels(img, boxes, rect, self.FLT_EPSILON_)        

            for j in xrange(0, region_labels.shape[0], 1):
                for i in xrange(0, region_labels.shape[1], 1):
                    if region_labels[j, i] == 1.0:
                        t = boxes[j, i]
                        box = np.array([rect[0] - t[0], rect[1] - t[1], \
                                        (rect[0] + rect[2]) - t[0], (rect[1] + rect[3]) - t[1]])
                        boxes_labels[k + 0, j, i] =  box[0]
                        boxes_labels[k + 1, j, i] =  box[1]
                        boxes_labels[k + 2, j, i] =  box[2]
                        boxes_labels[k + 3, j, i] =  box[3]

                        size_labels[k + 0, j, i] = 1.0 / rect[2]
                        size_labels[k + 1, j, i] = 1.0 / rect[3]
                        size_labels[k + 2, j, i] = 1.0 / rect[2]
                        size_labels[k + 3, j, i] = 1.0 / rect[3]

                        diff = np.float32(boxes[j, i][2] * boxes[j ,i][3]) / \
                               np.float32(rect[2] * rect[3])
                        obj_labels[k:k+channel_stride, j, i] = diff

                        coverage_label[k:k+channel_stride, j, i] = region_labels[j, i]
                    
                        foreground_labels[int(label), j, i] = self.FORE_PROB_

        return (foreground_labels, boxes_labels, size_labels, obj_labels, coverage_label)

    """
    Function to resize image and the labels
    """     
    def resize_image_and_labels(self, image, rects):
        resize_flag = (self.__net_size_x, self.__net_size_y)
        img_list = []
        resize_rects = []
        if resize_flag:
            for rect in rects:
                img = cv.resize(image, resize_flag, cv.INTER_CUBIC)
                img_list.append(img)
                # resize label
                ratio_x = np.float32(image.shape[1]) / np.float32(img.shape[1])
                ratio_y = np.float32(image.shape[0]) / np.float32(img.shape[0])

                x = np.float32(rect[0])
                y = np.float32(rect[1])
                w = np.float32(rect[2])
                h = np.float32(rect[3])
            
                xt = x / ratio_x
                yt = y / ratio_y
                xb = (x + w) / ratio_x
                yb = (y + h) / ratio_y
                
                rect_resize = (int(xt), int(yt), int(xb - xt), int(yb - yt))
                resize_rects.append(rect_resize)
        return img, resize_rects

    """
    Function random argumentation of images
    """     
    def random_argumentation(self, image, rects): 
        
        #! flip image
        flip_flag = random.randint(-1, 2)
        if flip_flag < 2 and flip_flag > -2:
            img_flip, rect_flips = self.flip_image(image.copy(), rects, flip_flag)
        else:
            img_flip = image.copy()
            rect_flips = rects

        #! zoom in
        is_crop = True  ##! ToDo: create union of all bounding box then crop
        if is_crop and len(rects) == 1:
            rect = rects[0]
            rect_flip = rect_flips[0]
            scale_x = np.float32(image.shape[1]) / np.float32(rect[2])
            scale_y = np.float32(image.shape[0]) / np.float32(rect[3])
            scale_x = int(math.floor(scale_x))
            scale_y = int(math.floor(scale_y))

            enlarge_factor1 = random.uniform(1.0, np.float32(scale_x/1.0))
            enlarge_factor2 = random.uniform(1.0, np.float32(scale_y/1.0))

            widths = (int(rect_flip[2] * enlarge_factor1), rect_flip[2] * enlarge_factor2)
            heights = (int(rect_flip[3] * enlarge_factor1), rect_flip[3] * enlarge_factor2)
            crop_image, crop_rect = self.crop_image_dimension(img_flip, rect_flip, \
                                                              widths, heights)
            rect_flips[0] = crop_rect
            img_flip = crop_image.copy()

        #! color arugmentation
        img_flip = self.color_space_argumentation(img_flip)

        #! rotate the image
        rot_image, rot_rects = self.rotate_image_with_rect(img_flip, rect_flips)

        #! normalize image
        rot_image = self.demean_rgb_image(rot_image)
        return (rot_image, rot_rects)

    """
    Function to crop image and the resize the rect
    """     
    def crop_image_dimension(self, image, rect, widths, heights):
        x = (rect[0] + rect[2]/2) - widths[0]
        y = (rect[1] + rect[3]/2) - heights[0]
        w = widths[1] + widths[0]
        h = heights[1] + heights[0]

        ## center 
        cx, cy = (rect[0] + rect[2]/2.0, rect[1] + rect[3]/2.0)
        shift_x, shift_y = (random.randint(0, int(w/2)), random.randint(0, int(h/2)))
        cx = (cx + shift_x) if random.randint(0, 1) else (cx - shift_x)
        cy = (cy + shift_y) if random.randint(0, 1) else (cy - shift_y)
        
        nx = int(cx - (w / 2))
        ny = int(cy - (h / 2))
        nw = int(w)
        nh = int(h)
        
        # img2 = image.copy()
        # cv.rectangle(img2, (nx, ny), (nx + nw, ny + nh), (0, 255, 0), 4)

        if nx > x:
            nx = x
            nw -=  np.abs(nx - x)
        if ny > y:
            ny = y
            nh -=  np.abs(ny - y)
        if nx + nw < x + w:
            nx += ((x+w) - (nx+nw))
        if ny + nh < y + h:
            ny += ((y+h) - (ny+nh))

        x = nx; y = ny; w = nw; h = nh
        # cv.rectangle(img2, (int(nx), int(ny)), (int(nx + nw), int(ny + nqh)), (255, 0, 255), 4)
        # cv.imshow("img2", img2)

        x = 0 if x < 0 else x
        y = 0 if y < 0 else y
        w = ((w - (w + x) - image.shape[1])) if x > image.shape[1] else w
        h = ((h - (h + y) - image.shape[0])) if y > image.shape[0] else h

        roi = image[int(y):int(y+h), int(x):int(x+w)].copy()
        new_rect = [int(rect[0] - x), int(rect[1] - y), rect[2], rect[3]]

        return roi, new_rect

    """
    Function flip image and rect around given axis
    """     
    def flip_image(self, image, rects, flip_flag = -1):
        im_flip = cv.flip(image, flip_flag)
        flip_rects = []
        for rect in rects:
            pt1 = (rect[0], rect[1])
            pt2 = (rect[0] + rect[2], rect[1] + rect[3])
            if flip_flag is -1:
                pt1 = (image.shape[1] - pt1[0] - 1, image.shape[0] - pt1[1] - 1)
                pt2 = (image.shape[1] - pt2[0] - 1, image.shape[0] - pt2[1] - 1)
            elif flip_flag is 0:
                pt1 = (pt1[0], image.shape[0] - pt1[1] - 1)
                pt2 = (pt2[0], image.shape[0] - pt2[1] - 1)
            elif flip_flag is 1:
                pt1 = (image.shape[1] - pt1[0] - 1, pt1[1])
                pt2 = (image.shape[1] - pt2[0] - 1, pt2[1])

            x = min(pt1[0], pt2[0])
            y = min(pt1[1], pt2[1])
            w = np.abs(pt2[0] - pt1[0])
            h = np.abs(pt2[1] - pt1[1])

            x = 0 if x < 0 else x
            y = 0 if y < 0 else y

            flip_rect = [x, y, w, h]
            flip_rects.append(flip_rect)
        return im_flip, flip_rects

    """
    Function to label each grid boxes based on IOU score
    """     
    def generate_box_labels(self, image, boxes, rect, iou_thresh):
        box_labels = np.zeros((boxes.shape[0], boxes.shape[1]))
        for j in xrange(0, boxes.shape[0], 1):
            for i in xrange(0, boxes.shape[1], 1):
                if self.__jc.iou(boxes[j, i], rect) > iou_thresh:
                    box_labels[j, i] = self.FORE_PROB_
        return box_labels

    """
    Function to overlay a grid on the image and return the boxes
    """     
    def grid_region(self, image, stride):
        wsize = (image.shape[0]/stride, image.shape[1]/stride)
        boxes = np.zeros((wsize[0], wsize[1], 4))
        for j in xrange(0, boxes.shape[0], 1):
            for i in xrange(0, boxes.shape[1], 1):
                boxes[j][i][0] = (i * stride)
                boxes[j][i][1] = (j * stride)
                boxes[j][i][2] = (stride)
                boxes[j][i][3] = (stride)
        return boxes

    """
    Function to demean rgb image using imagenet mean
    """
    def demean_rgb_image(self, im_rgb):
        im_rgb = im_rgb.astype(np.float32)
        im_rgb[:, :, 0] -= np.float32(104.0069879317889)
        im_rgb[:, :, 1] -= np.float32(116.66876761696767)
        im_rgb[:, :, 2] -= np.float32(122.6789143406786)
        im_rgb = (im_rgb - im_rgb.min())/(im_rgb.max() - im_rgb.min())
        return im_rgb

    """
    Function that aguments the image color space
    """
    def color_space_argumentation(self, image):
        seq = iaa.Sequential([
            iaa.OneOf([
                iaa.GaussianBlur((0, 3.0)),
                iaa.AverageBlur(k=(2, 7)),
                iaa.MedianBlur(k=(3, 7)),
            ]),
            iaa.Sharpen(alpha=(0, 1.0), lightness=(0.75, 1.5)),
            iaa.Add((-2, 21), per_channel=0.5),
            iaa.Multiply((0.75, 1.25), per_channel=0.5),
            iaa.ContrastNormalization((0.5, 1.50), per_channel=0.5),
            iaa.Grayscale(alpha=(0.0, 0.50)),
        ],
                             random_order=False)
        return seq.augment_image(image)

    """
    Function to rotate image and rect by random angle
    """
    def rotate_image_with_rect(self, image, rects):
        center = (image.shape[1]/2, image.shape[0]/2)
        angle = float(random.randint(-50, 50))  ##! TODO: add as hyperparam
        rot_mat = cv.getRotationMatrix2D(center, angle, 1)
        im_rot = cv.warpAffine(image, rot_mat, (image.shape[1], image.shape[0]))
        
        #! rotate rect
        rot_rects = []
        for rect in rects:
            x1 = rect[0] 
            y1 = rect[1]
            x2 = x1 + rect[2]
            y2 = y1 + rect[3]
            pt1x = int(x1 * rot_mat[0, 0] + y1 * rot_mat[0, 1] + rot_mat[0, 2])
            pt1y = int(x1 * rot_mat[1, 0] + y1 * rot_mat[1, 1] + rot_mat[1, 2])
            pt2x = int(x2 * rot_mat[0, 0] + y1 * rot_mat[0, 1] + rot_mat[0, 2])
            pt2y = int(x2 * rot_mat[1, 0] + y1 * rot_mat[1, 1] + rot_mat[1, 2])
            pt3x = int(x1 * rot_mat[0, 0] + y2 * rot_mat[0, 1] + rot_mat[0, 2])
            pt3y = int(x1 * rot_mat[1, 0] + y2 * rot_mat[1, 1] + rot_mat[1, 2])
            pt4x = int(x2 * rot_mat[0, 0] + y2 * rot_mat[0, 1] + rot_mat[0, 2])
            pt4y = int(x2 * rot_mat[1, 0] + y2 * rot_mat[1, 1] + rot_mat[1, 2])
            minx = min(pt1x, min(pt2x, min(pt3x, pt4x)))
            miny = min(pt1y, min(pt2y, min(pt3y, pt4y)))
            maxx = max(pt1x, max(pt2x, max(pt3x, pt4x)))
            maxy = max(pt1y, max(pt2y, max(pt3y, pt4y)))
            rect_rot = np.array([minx, miny, maxx-minx, maxy-miny])
            rot_rects.append(rect_rot)

        return im_rot, rot_rects

"""
while True:
    img=cv.imread('/home/krishneel/Desktop/dataset/cheezit/00000001.jpg')
    ae = ArgumentationEngine(448/2, 448/2, 16, 1)
    rects = np.array([[361, 198, 100, 134]])
    # , [195, 241, 305, 134], [25, 90, 402, 222],\
    #                   [203, 81, 128, 137], [235, 116, 44, 43]], np.int32)
    labels = np.array([0] #, 1, 2, 2, 2]
                      , np.int32)

    img2, rects2 = ae.random_argumentation(img, rects)
    img2, rects2 = ae.resize_image_and_labels(img2, rects2)

    a,b,c,d,e = ae.bounding_box_parameterized_labels(img2, rects2, labels)

    #z = np.hstack((a[0], a[1], a[2]))
    print img2.shape

    for rect in rects2:
        x,y,w,h = rect
        cv.rectangle(img2, (x,y), (w+x, h+y), (random.randint(0, 255), \
                                               random.randint(0, 255), random.randint(0, 255)),3)

    # for l in labels:
    #     aa = b[l*4:l*4+4]
    #     z = np.hstack((aa[0], aa[1], aa[2], aa[3]))
    #     import matplotlib.pyplot as plt
    #     plt.imshow(z)
    #     plt.show()
        
    cv.namedWindow('test', cv.WINDOW_NORMAL)
    cv.imshow('test', img2)    
    cv.namedWindow('mapo', cv.WINDOW_NORMAL)
    cv.imshow('mapo', a[0])    
    key = cv.waitKey(0)                                                                    
    if key == ord('q'):                                                                   
        break

"""
