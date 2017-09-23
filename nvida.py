import numpy as np
import pandas as pd
import simulator as sim
from math import sin, cos, acos
from time import time
from collections import defaultdict
from sklearn.metrics.pairwise import euclidean_distances

# username: tsiolkovski
# password: ts/14785

def rotate(axis, theta):
    '''
    Returns the rotation matrix given its axis and angle
    '''
    u_x, u_y, u_z = axis
    sin_theta = sin(theta)
    cos_theta = cos(theta)

    x = [cos_theta + u_x**2*(1 - cos_theta), 
         u_x*u_y*(1 - cos_theta) - u_z*sin_theta,
         u_x*u_z*(1 - cos_theta) + u_y*sin_theta]

    y = [u_y*u_x*(1 - cos_theta) + u_z*sin_theta, 
         cos_theta + u_y**2*(1 - cos_theta),
         u_y*u_z*(1 - cos_theta) - u_x*sin_theta]

    z = [u_z*u_x*(1 - cos_theta) - u_y*sin_theta, 
         u_z*u_y*(1 - cos_theta) + u_x*sin_theta,
         cos_theta + u_z**2*(1 - cos_theta)]

    return np.array([x, y, z]).reshape(3, 3)

def rotate_der(axis, theta):
    '''
    Returns the derivative of the rotation matrix given its axis and angle
    '''
    u_x, u_y, u_z = axis
    sin_theta = sin(theta)
    cos_theta = cos(theta)

    dx = [-sin_theta + u_x**2*(sin_theta), 
          u_x*u_y*(sin_theta) - u_z*cos_theta,
          u_x*u_z*(sin_theta) + u_y*cos_theta]

    dy = [u_y*u_x*(sin_theta) + u_z*cos_theta, 
          -sin_theta + u_y**2*(sin_theta),
          u_y*u_z*(sin_theta) - u_x*cos_theta]

    dz = [u_z*u_x*(sin_theta) - u_y*cos_theta, 
          u_z*u_y*(sin_theta) + u_x*cos_theta,
          -sin_theta + u_z**2*(sin_theta)]

    return np.array([dx, dy, dz]).reshape(3, 3)


class DistanceData:
    '''
    Class to store the data (froma csv file) of the distance between stars up 
    to a given magnitude
    '''
    def __init__(self, filename):
        self.df = pd.read_csv(filename, header=0, delimiter=',')
        self.star_count = None

    def starCount(self):
        '''
        Returns a dictionary where the key is the HIP code of a
        star and the value is the nuber of times it appears in the
        dataframe self.df
        '''
        star_count = defaultdict(int)
        for hip1, hip2 in zip(self.df['HIP1'], self.df['HIP2']):
            star_count[int(hip1)] += 1
            star_count[int(hip2)] += 1

        self.star_count = star_count


class InputScene:
    '''
    This class takes an scene as a string and extracts its info for later use 
    in the nvida algoritm
    '''
    def __init__(self, scene, camera):
        scene_array = np.array(scene.split(','), dtype = np.float64)
        assert scene_array.size % 3 == 0, 'The scene has the wrong number of rows'
        self.num_stars = scene_array.shape[0] // 3
        scene_matrix = scene_array.reshape(self.num_stars, 3)
        self.coordinates = scene_matrix[:, :2]
        self.magnitudes = scene_matrix[:, 2]
        self.max_magnitude = np.max(self.magnitudes)
        self.camera = camera
        self.distances = None

    @staticmethod
    def distanceFromCoor(star1_coor, star2_coor, camera):
        '''
        Return the arc distance between two stars given its coordinates in
        a scene and the camera used to take the image
        '''
        star1_az, star1_al = camera.to_angles(np.array([star1_coor]))
        star2_az, star2_al = camera.to_angles(np.array([star2_coor]))

        cenital_angle = star1_az - star2_az

        cenital_al1 = np.pi/2 - star1_al
        cenital_al2 = np.pi/2 - star2_al
        
        # Distance on the celestial sphere using the cosine rule
        arc_distance = acos(cos(cenital_al1)*cos(cenital_al2) +
                            sin(cenital_al1)*sin(cenital_al2)*cos(cenital_angle))
    
        return arc_distance

    def computeDistances(self):
        '''
        Computes the distance matrix of the scene. dist_matrix[i, j] is the 
        distance between the ith and jth stars of the scene if i < j, 
        0 otherwise
        '''
        dist_matrix = np.zeros((self.num_stars - 1, self.num_stars))
        for i in range(self.num_stars - 1):
            for j in range(i + 1, self.num_stars):
                dist_matrix[i, j] = InputScene.distanceFromCoor(self.coordinates[i], 
                                                                self.coordinates[j],
                                                                self.camera)
        self.distances = dist_matrix


class StarTriangle:
    '''
    This class represent the indexes of three stars from a scene and the
    HIP codes that have been asociated to them
    '''
    def __init__(self, ids, hips):
        self.vertices = dict(zip(ids, hips))
        self.ids = ids
        self.hips = hips
        self.centered_vertex = None
        self.left_vertices = None

    def findMostCenteredVertex(self, coordinates):
        '''
        Finds the id of the vertex closer to the image center, the other two 
        are assigned self.left_vertices
        '''
        center = np.array([[960, 720]])
        distances = euclidean_distances(coordinates[self.ids], center)

        self.centered_vertex = self.ids[np.argmin(distances)]
        ids_list = list(self.ids)
        ids_list.remove(self.centered_vertex)
        self.left_vertices = ids_list


class NvidaGradientDescent:
    '''
    Gradient descent, for the nvida algorithm, to fidn the best angle of 
    rotation (theta) to compute the rotation matrix
    '''
    def __init__(self, error, max_iterations):
        self.error = error
        self.max_iterations = max_iterations

    def findThetaZero(self, v1_camera, v2_camera, 
                      v1_celestial_rot, v2_celestial_rot, 
                      u_camera, orientation):
        '''
        Return theta, a number between 0 and 2*pi, that minimizes the cost
        function when evaluated at n points
        '''
        J = []
        n = 5
        thetas = np.linspace(0, (1-1/n)*2*np.pi, n)
        for theta in thetas:
            v1_rot = np.dot(rotate(u_camera, theta), v1_celestial_rot)
            v2_rot = np.dot(rotate(u_camera, theta), v2_celestial_rot)

            J.append((1 - np.dot(v1_camera[0], v1_rot)) + 
                     (1 - np.dot(v2_camera[0], v2_rot)))

        # Return the minimun value for J of the n that have been calculated
        return thetas[np.argmin(J)]

    def computeTheta(self, v1_camera, v2_camera, 
                     v1_celestial, v2_celestial, 
                     u, orientation):
        '''Returns the angle that minimize the sum of the cosine distance 
        between vectors: v1_camera, v1_celestial and v2_camera, v2_celestial'''
        eta = 35
        # u_camera is the vector u on the camera frame of reference 
        u_camera = np.dot(orientation, u)
        v1_celestial_rot = np.dot(orientation, v1_celestial)
        v2_celestial_rot = np.dot(orientation, v2_celestial)

        theta = self.findThetaZero(v1_camera, v2_camera, 
                                   v1_celestial_rot, v2_celestial_rot,    
                                   u_camera, orientation)

        iteration = 0
        converged = False
        while not converged and iteration < self.max_iterations:
            iteration += 1
            v1_der_rot = np.dot(rotate_der(u_camera, theta), v1_celestial_rot)
            v2_der_rot = np.dot(rotate_der(u_camera, theta), v2_celestial_rot)

            new_theta = theta + eta*(np.dot(v1_camera[0], v1_der_rot) +
                                     np.dot(v2_camera[0], v2_der_rot))

            if iteration == 250 or iteration == 500 or iteration == 1000:
                eta /= 2

            if abs(theta - new_theta) < self.error:
                converged = True

            theta = new_theta

        if not converged:
            print("didn't converge", end=' ')

        return theta


class Nvida:
    '''Normalized Voting, star IDentification Algorithm'''
    def __init__(self, catalog, camera, distance_data, 
                 dist_error=0.0003, mag_error=0.04,
                 dist_mult_factor=1.5, mag_mult_factor=1.5, 
                 max_num_triangles=50):
        self.catalog = catalog
        self.camera = camera
        self.distance_data = distance_data
        self.dist_error = dist_error
        self.mag_error = mag_error
        self.dist_mult_factor = dist_mult_factor
        self.mag_mult_factor = mag_mult_factor
        self.max_num_triangles = max_num_triangles
        self.votes_list = []
        self.tried_triangles = set()
        self.scene = None

    def identifyStars(self, scene):
        self.scene = scene
        match = False
        while not match:
            # t0 = time()
            filteredStars = self.filterStars()
            # print('time filtering:', time() - t0)
            self.countVotes(filteredStars)

            for triangle in self.triangleGeneratorBFS(filteredStars):
                # print(triangle.hips)
                triangle.findMostCenteredVertex(self.scene.coordinates)

                orientation_matrix = self.findOrientationMatrix(triangle)

                max_distance = self.maxDistanceFromCenteredVertex(triangle)

                limit = self.distance_data.df['distance'].searchsorted(max_distance)
                
                dist_filter = self.distance_data.df.iloc[:limit[0]]

                star0 = self.catalog.catalog[self.catalog.catalog['HIP'] == 
                                 triangle.vertices[triangle.centered_vertex]]

                mask = np.logical_or(dist_filter['HIP1'] == int(star0['HIP']), 
                                     dist_filter['HIP2'] == int(star0['HIP']))
                close_stars = dist_filter[mask]

                close_stars_hips = self.createHipsList(close_stars)

                coordinates, magnitudes = Nvida.closeStarsCoorMag(close_stars_hips, 
                                                                  orientation_matrix)
                # print(np.concatenate((coordinates, magnitudes), axis=1))
                # print(np.concatenate((scene.coordinates, scene.magnitudes.reshape(len(scene.magnitudes),1)), axis=1))

                match, scene_ids = self.doesMatch(coordinates, magnitudes, 
                                                  close_stars_hips)

                if match or len(self.tried_triangles) >= self.max_num_triangles:
                    break

            if len(self.tried_triangles) >= self.max_num_triangles and not match:
                scene_ids = ['-1'] * scene.num_stars
                break

            elif not match:
                self.dist_error *= self.dist_mult_factor
                self.mag_error *= self.mag_mult_factor
                # print(self.mag_error, self.dist_error)

        return match, scene_ids


    def filterStars(self):
        filteredStars = [[] for i in range(self.scene.num_stars)]
        for i in range(self.scene.num_stars - 1):
            for j in range(i + 1, self.scene.num_stars):
                distance = self.scene.distances[i, j]
                # As distance_data is sorted by distance, we can make use of binary search
                bounds = self.distance_data.df['distance'].searchsorted([distance - self.dist_error, 
                                                                         distance + self.dist_error])
                lower_bound, upper_bound = bounds 
                # Once we have the lower and upper bounds we filter the data          
                data_filtered = self.distance_data.df.iloc[lower_bound:upper_bound]         

                i_inf, j_inf = scene.magnitudes[[i, j]] - self.mag_error
                i_sup, j_sup = scene.magnitudes[[i, j]] + self.mag_error
                # Last we filter by magnitude
                for hip1, hip2, mag1, mag2 in zip(data_filtered['HIP1'], 
                                                  data_filtered['HIP2'], 
                                                  data_filtered['Vmag1'], 
                                                  data_filtered['Vmag2']):
                    if (i_inf < mag1 < i_sup and j_inf < mag2 < j_sup or
                        j_inf < mag1 < j_sup and i_inf < mag2 < i_sup):
                        filteredStars[i].append((int(hip1), int(hip2), j))
                        filteredStars[j].append((int(hip1), int(hip2), i))

        return filteredStars

    def countVotes(self, filteredStars):
        self.votes_list = []
        for star in filteredStars:
            dic_ids = defaultdict(int)
            for hip1, hip2, index in star:
                dic_ids[hip1] += 1 
                dic_ids[hip2] += 1
            normalized_vote = lambda x: x[1]/self.distance_data.star_count[x[0]]
            self.votes_list.append(sorted(list(dic_ids.items()), 
                                          key=normalized_vote, 
                                          reverse=True))

    def triangleGeneratorBFS(self, filteredStars):
        '''Generates all posible triangles. "Breadth first search"'''
        deepness = 0
        stars_left = list(range(len(self.votes_list)))
        while stars_left:
            for id1 in stars_left:
                count = 0
                if 0 < len(self.votes_list[id1]) and len(self.votes_list[id1]) > deepness:
                    hip, count = self.votes_list[id1][deepness]
                if count > 1:
                    hip1 = hip
                else:
                    stars_left.remove(id1)
                    continue
                candidates_list1 = [tupla for tupla in filteredStars[id1] 
                                    if hip1 in [tupla[0], tupla[1]]]
                for hip_candidate1, hip_candidate2, id2 in candidates_list1:
                    if hip_candidate1 != hip1:
                        hip2 = hip_candidate1
                    else:
                        hip2 = hip_candidate2
                    candidates_list2 = [tupla for tupla in filteredStars[id2] 
                                        if hip2 in [tupla[0], tupla[1]] and 
                                           hip1 not in [tupla[0], tupla[1]]]
                    for hip_candidate3, hip_candidate4, id3 in candidates_list2:
                        if hip_candidate3 != hip2:
                            hip3 = hip_candidate3
                        else:
                            hip3 = hip_candidate4
                        if tuple(sorted([hip1, hip3])+[id1]) in filteredStars[id3]:
                            triangle = StarTriangle([id1, id2, id3], [hip1, hip2, hip3])
                            triangle_hips = frozenset(triangle.hips)
                            if triangle_hips not in self.tried_triangles:
                                self.tried_triangles.add(triangle_hips)
                                yield triangle
            deepness += 1

    def findOrientationMatrix(self, triangle):
        star0 = self.catalog.catalog[self.catalog.catalog['HIP'] == 
                                     triangle.vertices[triangle.centered_vertex]]
        x0, y0 = scene.coordinates[triangle.centered_vertex]
        az0, al0 = self.camera.to_angles(np.array([[y0, x0]]))

        star1 = self.catalog.catalog[self.catalog.catalog['HIP'] == 
                                     triangle.vertices[triangle.left_vertices[0]]]
        x1, y1 = scene.coordinates[triangle.left_vertices[0]]
        az1, al1 = self.camera.to_angles(np.array([[y1, x1]]))

        star2 = self.catalog.catalog[self.catalog.catalog['HIP'] == 
                                     triangle.vertices[triangle.left_vertices[1]]]
        x2, y2 = scene.coordinates[triangle.left_vertices[1]]
        az2, al2 = self.camera.to_angles(np.array([[y2, x2]]))

        u = sim.angles_to_vector(float(np.deg2rad(star0['RAdeg'])), 
                                 float(np.deg2rad(star0['DEdeg'])))

        v1_camera = sim.angles_to_vector(az1, al1)
        v2_camera = sim.angles_to_vector(az2, al2)

        v1_celestial = sim.angles_to_vector(float(np.deg2rad(star1['RAdeg'])), 
                                            float(np.deg2rad(star1['DEdeg'])))
        v2_celestial = sim.angles_to_vector(float(np.deg2rad(star2['RAdeg'])), 
                                            float(np.deg2rad(star2['DEdeg'])))

        orientation = sim.lookat(u)
        rot_axis = np.array([np.sin(az0), -np.cos(az0), 0], dtype=np.float64)
        angle = np.pi/2 - al0
        orientation2 = np.dot(rotate(rot_axis, -angle), orientation)

        gradient_descent = NvidaGradientDescent(error=1e-5, max_iterations=1500 )

        theta = gradient_descent.computeTheta(v1_camera, v2_camera,
                                              v1_celestial, v2_celestial,
                                              u, orientation2)
        u2 = np.dot(orientation2, u)

        return np.dot(rotate(u2, theta), orientation2)

    def maxDistanceFromCenteredVertex(self, triangle):
        tri_vertex_coor = self.scene.coordinates[triangle.centered_vertex][::-1]
        vertices_coor = [[   0,    0],
                         [   0, 1920],
                         [1440,    0],
                         [1440, 1920]]

        distances = np.zeros(4)
        for index, coordinates in enumerate(vertices_coor):
            distances[index] = InputScene.distanceFromCoor(tri_vertex_coor, 
                                                           coordinates,
                                                           self.camera)
        return np.max(distances) + 0.002

    def createHipsList(self, close_stars):
        hips_set = set()
        for hip1, hip2, mag1, mag2 in zip(close_stars['HIP1'], close_stars['HIP2'], 
                                          close_stars['Vmag1'], close_stars['Vmag2']):
            if mag1 < self.scene.max_magnitude + 0.4:
                hips_set.add(int(hip1))
            if mag2 < self.scene.max_magnitude + 0.4:   
                hips_set.add(int(hip2))

        return np.array(list(hips_set))

    @staticmethod
    def closeStarsCoorMag(hips, orientation_matrix):
        star_vectors = np.zeros((len(hips), 3))
        magnitudes = np.zeros((len(hips), 1))

        for i in range(len(hips)):
            present_star = catalog.catalog[catalog.catalog['HIP'] == hips[i]]
            star_vectors[i] = sim.angles_to_vector(float(np.deg2rad(present_star['RAdeg'])), 
                                                   float(np.deg2rad(present_star['DEdeg'])))
            magnitudes[i] = present_star['Vmag']

        pos = np.dot(star_vectors, orientation_matrix.transpose())
        az, alt = sim.vector_to_angles(pos)
        coordinates = camera.from_angles(az, alt)[:, ::-1]

        return coordinates, magnitudes

    def doesMatch(self, coordinates, magnitudes, hips):
        match = True
        doble_star = False
        scene_ids = ['-1'] * self.scene.num_stars
        for i in range(magnitudes.size):
            candidates = []
            for j in range(self.scene.magnitudes.size):
                distance_pos = np.linalg.norm(coordinates[i] - self.scene.coordinates[j])
                distance_mag = abs(magnitudes[i] - self.scene.magnitudes[j])
                if (distance_pos < 1 and distance_mag < 0.2 or
                    distance_pos < 2 and distance_mag < 0.12 or
                    distance_pos < 3 and distance_mag < 0.08):

                    candidates.append(j)

            in_image = Nvida.isInImage(coordinates[i], magnitudes[i], 
                                       self.scene.max_magnitude)
            if len(candidates) == 0 and in_image:
                match = False

            elif len(candidates) == 1:
                scene_ids[candidates[0]] = str(hips[i])

            elif len(candidates) > 1:
                # print(candidates)
                for k in candidates:
                    scene_ids[k] = 'DS'
                    doble_star = True
                # min_distance = np.inf
                # for k in candidates:
                #     distance = abs(magnitudes[i] - scene.magnitudes[j])
                #     if distance < min_distance:
                #         min_distance = distance
                #         candidate = k
                # scene_ids[candidate] = str(hips[i])

        total_stars = self.scene.num_stars - scene_ids.count('-1')
        if total_stars < 3:
            match = False
        if doble_star:
            for i in range(len(scene_ids)):
                scene_ids[i] = scene_ids[i].replace('DS', '-1')


        return match, scene_ids

    @staticmethod
    def isInImage(coordinates, magnitude, max_mag):
        '''
        Returns True if the star, with the given coordinates and magnitude, is
        in the image under certain error margin. False otherwise
        '''
        error_pixels = 3
        error_mag = 0.3
        in_image = (error_pixels < coordinates[0] < res_x - error_pixels and 
                    error_pixels < coordinates[1] < res_y - error_pixels and 
                    magnitude < max_mag - error_mag)

        return in_image


if  __name__ == '__main__':
    
    # resolution
    res_x = 1920 # pixels
    res_y = 1440 # pixels
    # field of view
    fov = 10
    # normalized focal length
    f = 0.5 / np.tan(np.deg2rad(fov) / 2)
    # pixel aspect ratio
    pixel_ar = 1
    # normalized principal point
    ppx = 0.5
    ppy = 0.5

    cam = 0
    cameras = [sim.RectilinearCamera,
               sim.EquidistantCamera,
               sim.EquisolidAngleCamera,
               sim.StereographicCamera,
               sim.OrthographicCamera]

    camera = cameras[cam](f, (res_x, res_y), pixel_ar, (ppx, ppy))

    print()
    print('Loading the star catalog...')
    t0 = time()
    catalog = sim.StarCatalog('data\\hip_main.dat')
    print('Catalog loaded in {} seconds'.format(round(time() - t0, 2)))
    print()

    with open('input_sample.csv', 'r') as input_file, \
         open('result.csv', 'w') as output_file:

        print('Loading the distance data and counting stars...')
        t1 = time()
        distance_data = DistanceData('distance_data\\distance_data60.csv')  
        distance_data.starCount() 
        print('Done in {} seconds'.format(round(time() - t1, 2)))
        print()

        t2 = time()
        print('-----------------------------')
        print()

        total_no_match = 0
        global_triangles = 0

        for scene_num, line in enumerate(input_file, start=1):
            t3 = time()
            print(scene_num, end=' ')

            # Initiliazing the scene and computing its distances
            scene = InputScene(line, camera)
            # print('number of stars:', scene.num_stars)
            scene.computeDistances()

            # Initiliazing the algorithm
            nvida = Nvida(catalog, camera, distance_data, 
                          dist_error=0.0003, 
                          mag_error=0.04,
                          dist_mult_factor=1.5, 
                          mag_mult_factor=1.5, 
                          max_num_triangles=200)
            match, scene_ids = nvida.identifyStars(scene)

            if not match:
                total_no_match += 1
                print('not found', total_no_match)
            else:
                print()

            global_triangles += len(nvida.tried_triangles)

            output_file.write(','.join(scene_ids) + '\n')

        print('total time:', time() - t2)
        print('total not found:', total_no_match)
        print('total triangles:', global_triangles)
