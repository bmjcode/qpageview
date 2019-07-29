# This file is part of the qpageview package.
#
# Copyright (c) 2010 - 2019 by Wilbert Berendsen
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# See http://www.gnu.org/licenses/ for more information.


"""
Manages lists of rectangular objects and quickly finds them.
"""

import bisect
import operator


Left   = 0
Top    = 1
Right  = 2
Bottom = 3


class Rectangles:
    """
    Manages a list of rectangular objects and quickly finds objects at
    some point, in some rectangle or intersecting some rectangle.

    The implementation uses four lists of the objects sorted on either
    coordinate, so retrieval is fast.

    Bulk adding is done in the constructor or via the bulk_add() method (which
    clears the indexes, that are recreated on first search).  Single objects
    can be added and deleted, keeping the indexes, but that's slower.

    You should inherit from this class and implement the method get_coords(obj)
    to get the rectangle of the object (x, y, x2, y2). These are requested only
    once. x should be < x2 and y should be < y2.
    
    """
    def __init__(self, objects=None):
        """Initializes the Rectangles object.

        objects should, if given, be an iterable of rectangular objects, and
        bulk_add() is called on those objects.
        
        """
        self._items = {} # maps object to the result of func(object)
        self._index = {} # maps side to indices, objects (index=coordinate of that side)
        if objects:
            self.bulk_add(objects)

    def get_coords(self, obj):
        """You should implement this method.
        
        The result should be a four-tuple with the coordinates of the rectangle
        the object represents (x, y, x2, y2). These are requested only once.
        x should be < x2 and y should be < y2.
        
        """
        return (0, 0, 0, 0)
    
    def add(self, obj):
        """Adds an object to our list. Keeps the index intact."""
        if obj in self._items:
            return
        self._items[obj] = coords = self.get_coords(obj)
        for side, (indices, objects) in self._index.items():
            i = bisect.bisect_left(indices, coords[side])
            indices.insert(i, coords[side])
            objects.insert(i, obj)

    def bulk_add(self, objects):
        """Adds many new items to the index using the function given in the constructor.

        After this, the index is cleared and recreated on the first search operation.

        """
        self._items.update((obj, self.get_coords(obj)) for obj in objects)
        self._index.clear()

    def remove(self, obj):
        """Removes an object from our list. Keeps the index intact."""
        del self._items[obj]
        for indices, objects in self._index.values():
            i = objects.index(obj)
            del objects[i]
            del indices[i]

    def clear(self):
        """Empties the list of items."""
        self._items.clear()
        self._index.clear()

    def at(self, x, y):
        """Returns a set() of objects that are touched by the given point."""
        return self._test(
            (self._smaller, Top, y),
            (self._larger, Bottom, y),
            (self._smaller, Left, x),
            (self._larger, Right, x))

    def inside(self, left, top, right, bottom):
        """Returns a set() of objects that are fully in the given rectangle."""
        return self._test(
            (self._larger, Top, top),
            (self._smaller, Bottom, bottom),
            (self._larger, Left, left),
            (self._smaller, Right, right))

    def intersecting(self, left, top, right, bottom):
        """Returns a set() of objects intersecting the given rectangle."""
        return self._test(
            (self._smaller, Top, bottom),
            (self._larger, Bottom, top),
            (self._smaller, Left, right),
            (self._larger, Right, left))

    def width(self, obj):
        """Return the width of the specified object.

        This can be used for sorting a set returned by at(), inside() or
        intersecting(). For example:

            for r in sorted(rects.at(10, 20), key=rects.width):
                # ...

        """
        coords = self._items[obj]
        return coords[Right] - coords[Left]

    def height(self, obj):
        """Return the height of the specified object. See also width()."""
        coords = self._items[obj]
        return coords[Bottom] - coords[Top]

    def closest(self, obj, side):
        """Returns the object closest to the given one, going to the given side."""
        coords = self._items[obj]
        pos = coords[side^2]
        lat = (coords[side^1|2] - coords[side^1&2]) / 2.0
        direction = -1 if side < Right else 1
        indices, objects = self._sorted(side^2)
        i = objects.index(obj)
        mindist = indices[-1]
        result = []
        for other in objects[i+direction::direction]:
            coords = self._items[other]
            pos1 = coords[side^2]
            d = abs(pos1 - pos)
            if d > mindist:
                break
            lat1 = (coords[side^1|2] - coords[side^1&2]) / 2.0
            dlat = abs(lat1 - lat)
            if dlat < d:
                dist = dlat + d  # manhattan dist
                result.append((other, dist))
                mindist = min(mindist, dist)
        if result:
            result.sort(key=lambda r: r[1])
            return result[0][0]

    def nearest(self, x, y):
        """Return the object with the shortest distance to the point x, y.
        
        The point (x, y) can be outside the object. If there are no objects,
        None is returned. If multiple objects contain (x, y), the one that is
        closest to the center is returned.
        
        """
        i = self._items
        
        # find objects that contain (x, y)
        rmid = self._test((self._smaller, Top, y), (self._larger, Bottom, y))
        cmid = self._test((self._smaller, Left, x), (self._larger, Right, x))
        mid = rmid & cmid
        if mid:
            def center_distance(obj):
                left, top, right, bottom = i[obj]
                centerx = (right  + left) / 2
                centery = (bottom + top)  / 2
                return abs(centerx - x) + abs(centery - y)  # manhattan dist
            return min(mid, key=center_distance)
        
        # make sets for objects that are at our left (cleft) or right (cright)
        # and that are above us (rtop) or below us (rbottom)
        cleft = set(self._larger(Left, x))
        cright = set(self._smaller(Right, x))
        rtop = set(self._larger(Top, y))
        rbottom = set(self._smaller(Bottom, y))
        
        left =        lambda o: i[o][Left] - x
        right =       lambda o: x - i[o][Right]
        top =         lambda o: i[o][Top] - y
        bottom =      lambda o: y - i[o][Bottom]
        topleft =     lambda o: top(o) + left(o)
        topright =    lambda o: top(o) + right(o)
        bottomleft =  lambda o: bottom(o) + left(o)
        bottomright = lambda o: bottom(o) + right(o)
        
        # then find objects that have (x, y) closest at one of their sides
        result = [min((dist(o), o) for o in objs)
            for dist, objs in (
            # edges
            (left, cleft & rmid),          (right, cright & rmid),
            (top, rtop & cmid),            (bottom, rbottom & cmid),
            # corners
            (topleft, cleft & rtop),       (topright, cright & rtop),
            (bottomleft, cleft & rbottom), (bottomright, cright & rbottom),
            ) if objs]
        if result:
            return min(result)[1]

    def __len__(self):
        """Return the number of objects."""
        return len(self._items)

    def __contains__(self, obj):
        """Return True if the object is managed by us."""
        return obj in self._items

    def __bool__(self):
        """Always return True."""
        return True

    # private helper methods
    def _test(self, *tests):
        """Performs tests and returns objects that fulfill all of them.

        Every test should be a three tuple(method, side, value).
        Method is either self._smaller or self._larger.
        Returns a (possibly empty) set.

        """
        meth, side, value = tests[0]
        result = set(meth(side, value))
        if result:
            for meth, side, value in tests[1:]:
                result &= set(meth(side, value))
                if not result:
                    break
        return result

    def _smaller(self, side, value):
        """Returns objects for side below value."""
        indices, objects = self._sorted(side)
        i = bisect.bisect_right(indices, value)
        return objects[:i]

    def _larger(self, side, value):
        """Returns objects for side above value."""
        indices, objects = self._sorted(side)
        i = bisect.bisect_left(indices, value)
        return objects[i:]

    def _sorted(self, side):
        """Returns a two-tuple (indices, objects) sorted on index for the given side."""
        try:
            return self._index[side]
        except KeyError:
            if self._items:
                objects = [(coords[side], obj) for obj, coords in self._items.items()]
                objects.sort(key=operator.itemgetter(0))
                result = tuple(map(list, zip(*objects)))
            else:
                result = [], []
            self._index[side] = result
            return result


