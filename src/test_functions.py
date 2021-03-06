#!/usr/bin/env python

import rospy
import roslib; roslib.load_manifest( 'semap_ros' )

from sqlalchemy.orm import aliased, join

from db_model import *
from db_environment import db
from semap_ros.srv import *
from semap.ros_postgis_conversion import *

from semap_ros.subqueries import *
'''
SEMAP Spatial Relations Services
'''

def extrude_polygon( req ):
  res = ExtrudePolygonResponse()
  rospy.loginfo( "SEMAP DB SRVs: extrude_polygon" )
  mesh = db().execute( SFCGAL_Extrude( fromPolygon2D( req.polygon), req.vector.x, req.vector.y, req.vector.z) ).scalar()
  res.mesh = toPolygonMesh3D( mesh )
  return res

def get_absolute_geometry( id, type ):
  rospy.loginfo( "SEMAP DB SRVs: get_absolute_geometry" )
  then = rospy.Time.now()
  obj = db().query( ObjectInstance ).filter( ObjectInstance.id == id ).one()
  print obj.id, obj.name, obj.object_description.type
  for model in obj.object_description.geometry_models:
    if model.type == type:
      break
  #then2 = rospy.Time.now()
  #geometry = model.geometry
  #rospy.loginfo( "Look: %fs" % ( rospy.Time.now() - then2 ).to_sec() )
  then3 = rospy.Time.now()
  transformed_model = model.transformed()
  #rospy.loginfo( "Trans: %fs" % ( rospy.Time.now() - then3 ).to_sec() )
  then4 = rospy.Time.now()
  absolute_model = obj.frame.apply( transformed_model )
  #rospy.loginfo( "Abs: %fs" % ( rospy.Time.now() - then4 ).to_sec() )
  #print 'raw         ', db().execute( ST_AsText( geometry ) ).scalar()
  #print 'transformed ', db().execute( ST_AsText( transformed_model ) ).scalar()
  #print 'absolute    ', db().execute( ST_AsText( absolute_model ) ).scalar()
  #rospy.loginfo( "Total: %fs" % ( rospy.Time.now() - then ).to_sec() )
  return absolute_model

def unary_relation_test( req ):
  rospy.loginfo( "SEMAP DB SRVs: unary_relation_test" )
  geo = get_absolute_geometry( req.id, req.type )
  if "area" or "all" in req.relations:
    area = db().execute( SFCGAL_Area( ST_AsText( geo ) ) ).scalar()
    print 'area:', area
  if "area3d" or "all" in req.relations:
    area = db().execute( SFCGAL_3DArea( ST_AsText( geo ) ) ).scalar()
    print 'area:3d', area
  if "volume" or "all" in req.relations:
    area = db().execute( SFCGAL_Volume( ST_AsText( geo ) ) ).scalar()
    print 'volume:', area
  if "convexhull" or "all" in req.relations:
      hull = db().execute( ST_AsText( SFCGAL_3DConvexhull( geo ) ) ).scalar()
      print 'convexhull:', hull
  return

def binary_relation_test( req ):
  rospy.loginfo( "SEMAP DB SRVs: binary_relation_test" )
  print 'Called BinaryRelationsTest with', req.relations
  res = BinaryRelationTestResponse()
  geo1 = get_absolute_geometry( req.id1, req.type1 )
  geo2 = get_absolute_geometry( req.id2, req.type2 )
  #print 'GEO1'
  #print db().execute( ST_AsText( geo1 ) ).scalar()
  #print 'GEO2'
  #print db().execute( ST_AsText( geo1 ) ).scalar()
  result_collections = []
  #if "intersects" or "all" in req.relations:
    #intersects = db().execute( SFCGAL_3DIntersects( ST_AsText( geo1 ),ST_AsText( geo2 ) ) ).scalar()
    #print 'intersects:', intersects
  if "intersection" in req.relations or "all" in req.relations:
    print "INTERSECTION"
    data = db().execute( ST_AsText( SFCGAL_3DIntersection( geo1,geo2 ) ) ).scalar()
    result = LabeledGeometryCollection()
    addToCollection( data, result.collection )
    result.label = 'Intersection'
    res.results.append( result )
  if "difference" in req.relations or "all" in req.relations:
    print "DIFFERENCE"
    data = db().execute( ST_AsText( SFCGAL_3DDifference( ST_AsText( geo1 ),ST_AsText( geo2 ) ) ) ).scalar()
    result2 = LabeledGeometryCollection()
    print data
    addToCollection( data, result2.collection )
    result2.label = 'Difference'
    res.results.append( result2 )
  if "union" in req.relations or "all" in req.relations:
    print
    print "UNION"
    data = db().execute( ST_AsText( SFCGAL_3DUnion( ST_AsText( geo1 ),ST_AsText( geo2 ) ) ) ).scalar()
    print data
    result3 = LabeledGeometryCollection()
    addToCollection( data, result3.collection )
    result3.label = 'Union'
    res.results.append( result3 )
  return res

#>>> adalias1 = aliased( Address )
#>>> adalias2 = aliased( Address )
#sql
#>>> for username, email1, email2 in \
#...     session.query( User.name, adalias1.email_address, adalias2.email_address ).\
#...     join( adalias1, User.addresses ).\
#...     join( adalias2, User.addresses ).\
#...     filter( adalias1.email_address=='jack@google.com' ).\
#...     filter( adalias2.email_address=='j25@yahoo.com' ):
#...     print username, email1, email2

def test_retrieval( req ):
  rospy.loginfo( "SEMAP DB SRVs: test_distance" )
  then = rospy.Time.now()

  origin = WKTElement( 'POINT( %f %f %f )' % ( 0.0, 0.0, 0.0 ) )

  geo0 = aliased( GeometryModel )
  geo1 = aliased( GeometryModel )
  obj1 = aliased( ObjectInstance )
  obj2 = aliased( ObjectInstance )

  anyobj =  db().query( geo0.geometry ).filter( geo0.type == "Body", obj1.absolute_description_id == geo0.object_description_id ).label( "any" )
  res0 =  db().query( geo0.geometry ).filter( obj1.id == 2, geo0.type == "Body", obj1.absolute_description_id == geo0.object_description_id ).label( "res0" )
  res1 =  db().query( geo1.geometry ).filter( obj2.id == 3, geo1.type == "Body", obj2.absolute_description_id == geo1.object_description_id ).label( "res1" )

  root_dist = SFCGAL_Distance3D( origin, res0 ).label( "root_dist" )
  in_root_range = db().query( obj1.id, root_dist ).filter( root_dist > 2.0 )
  print in_root_range.all()

  #obj_dist = SFCGAL_Distance3D( res0, res1 ).label( "obj_dist" )
  #in_obj_range = db().query( obj1.id, obj2.id, obj_dist ).filter( obj_dist > 0.0 )
  #print in_obj_range.all()

  intersects = db().query( obj1.id, obj2.id, SFCGAL_Intersects3D( res0, res1 ) ).filter( obj1.id != obj2.id )
  print intersects.all()

  #dist = db().query( obj1.id,  ).filter( SFCGAL_Distance3D( WKTElement( 'POINT( %f %f %f )' % ( 0.0, 0.0, 0.0 ) ), res0 ) > 2.0 )#.label( "dist" )
  #inrange = db().query( obj1 ).filter( SFCGAL_Distance3D( WKTElement( 'POINT( %f %f %f )' % ( 0.0, 0.0, 0.0 ) ), res0 ) > 2.0 )#.label( "dist" )

  #inrange = db().query( obj1.id ).filter( dist > 0.0 ).all()
  #print dist
  #for o in dist:
  #  print o

  #resres0 =  db().query( geo0.geometry ).select_from( join( geo0, ObjectInstance ) ).filter( ObjectInstance.id == 3, ObjectInstance.absolute_description_id == GeometryModel.object_description_id ).all()
  #
  #print 'frist', len( resres0 )

  #for g in resres0:
    #print db().execute( ST_AsText( g ) ).scalar()
    #print i.name, g.type
  #print 'second'
  #for i, g in res1:
    #print i.name, g.type

  #print 'disttest', db().query( ST_Distance( resres0, WKTElement( 'POINT( 1.0 0.0 0.0 )' ) ) ).scalar()

  # laeuft
 ## print 'disttest', db().query( ObjectInstance.id ).filter( ST_Distance( ObjectInstance.tester(), WKTElement( 'POINT( 1.0 0.0 0.0 )' ) ) > 0 ).all()

  #print 'disttest', db().query( ObjectInstance.id ).filter( ST_Distance( ObjectInstance.tester2(), WKTElement( 'POINT( 1.0 0.0 0.0 )' ) ) > 0 ).all()
  #print 'disttest', db().query( ObjectInstance.id ).filter( ST_Distance( WKTElement( 'POINT( 1.0 0.0 0.0 )' ), WKTElement( 'POINT( 1.0 0.0 0.0 )' ) ) > 0 ).all()
  #obj1.id, obj2.id ).filter( db().execute( ST_DWithin( obj1.getAPosition2D() , obj2.getAPosition2D(), 20.0 ) ) ): #ST_DWithin( obj1.getAPosition2D() , obj2.getAPosition2D(), 2.0 )
  #dat = db().exists().where( db().execute( ST_Within( origin , ObjectInstance.getAPosition2D() ) ) )
  #obj_within_range = db().query( ObjectInstance ).filter( ST_Within( origin , ObjectInstance.getAPosition2D ) ).all()

 ## print 'disttest', db().query( ObjectInstance, ObjectInstance.frame ).filter( ST_Distance( ObjectInstance.tester2(), WKTElement( 'POINT( 1.0 0.0 0.0 )' ) ) > 0 ).all()
  return GetObjectInstancesResponse()

def test_create_absolute_description( req ):
  rospy.loginfo( "SEMAP DB SRVs: test_create_absolute_description" )
  then = rospy.Time.now()
  res = GetObjectInstancesResponse()
  objects = db().query( ObjectInstance ).filter( ObjectInstance.id.in_( req.ids ) ).all()

  for obj in objects:
    print "Create Absolute for", obj.name
    obj.createAbsoluteDescription()

  return res

def test_object_instances( req ):
  rospy.loginfo( "SEMAP DB SRVs: test_object_instances" )
  then = rospy.Time.now()
  res = GetObjectInstancesResponse()
  objects = db().query( ObjectInstance ).filter( ObjectInstance.id.in_( req.ids ) ).all()

  for obj in objects:
    then2 = rospy.Time.now()

    #print 'coll',  obj.object_description.getGeometryCollection()
    #print 'coll aT', obj.object_description.getGeometryCollection( as_text = True )

    #print 'box', obj.object_description.getBoundingBox()
    #print 'box aT', obj.object_description.getBoundingBox( as_text = True )

    #print 'box2d', obj.object_description.getBox2D()
    #print 'box3d', obj.object_description.getBox3D()
    #print 'box3d mesh', box3DtoPolygonMesh( obj.object_description.getBox3D() )

    #print 'ch2d', obj.object_description.getConvexHull2D()
    #print 'ch2dt', obj.object_description.getConvexHull2D( True )

    pos2D = obj.getAPosition2D()
    pos3D = obj.getAPosition3D()
    print 'pos2D', db().execute( ST_AsText( obj.getAPosition2D() ) ).scalar()
    print 'pos3D', db().execute( ST_AsText( obj.getAPosition3D() ) ).scalar()
    #geom2D_1 = obj.getAConvexHull2D()
    geom2D_1 = origin
    #obj.getABox2D()
    #geom2D_2 = obj.getABox2D()
    geom2D_2 = obj.getAConvexHull2D()
    geom2D_2 = pos2D

    #geom3D_1 = obj.getAConvexHull3D()
    geom3D_1 = origin
    #geom3D_1 = origin
    #geom3D_2 = obj.getABox3D()
    #geom3D_2 = obj.getAConvexHull3D()
    geom3D_2 = pos3D

    print '## 2D ##'

    print '2d distance', db().execute( ST_Distance( geom2D_2 , geom2D_1 ) ).scalar()
    print '2d in range', db().execute( ST_DWithin( geom3D_1 , geom3D_2, 0.0 ) ).scalar()
    # no fully within 2D geometry fzunc
    #print '2d fully in range', db().execute( ST_DFullyWithin( geom3D_1 , geom3D_2, 4.0 ) ).scalar()

    print '2d within', db().execute( ST_Within( geom2D_1 , geom2D_2 ) ).scalar()
    print '2d contains', db().execute( ST_Contains( geom2D_1 , geom2D_2 ) ).scalar()

    print '2d touches', db().execute( ST_Touches( geom2D_1 , geom2D_2 ) ).scalar()
    print '2d intersects', db().execute( ST_Intersects( geom2D_1 , geom2D_2 ) ).scalar()
    print '2d disjoint', db().execute( ST_Disjoint( geom2D_1 , geom2D_2 ) ).scalar()

    print '## 3D ##'
    print 'in range', db().execute( ST_3DDWithin( geom3D_1 , geom3D_2, 0.0 ) ).scalar()
    print 'fully in range', db().execute( ST_3DDFullyWithin( geom3D_1 , geom3D_2, 4.0 ) ).scalar()

    print 'min distance', db().execute( ST_3DDistance( geom3D_1 , geom3D_2 ) ).scalar()
    print 'max distance', db().execute( ST_3DMaxDistance( geom3D_1 , geom3D_2 ) ).scalar()

    print 'min line', db().execute( ST_AsText( ST_3DShortestLine( geom3D_1 , geom3D_2 ) ) ).scalar()
    print 'max line', db().execute( ST_AsText( ST_3DLongestLine( geom3D_1 , geom3D_2 ) ) ).scalar()

    #print ' OTHER '
    #print 'skeleton', db().execute( ST_AsText( ST_StraightSkeleton( geom2D_1 ) ) ).scalar()
    #print 'skeleton', db().execute( ST_AsText( ST_StraightSkeleton( geom3D_1 ) ) ).scalar()

  rospy.loginfo( "Get Test took %f seconds in total." % ( rospy.Time.now() - then ).to_sec() )
  return res

def test_ecmr( req ):
  rospy.loginfo( "SEMAP DB SRVs: test_ecmr" )
  then = rospy.Time.now()

  origin = WKTElement( 'POINT( %f %f %f )' % ( 0.0, 0.0, 0.0 ) )

  geo1 = aliased( GeometryModel )
  obj1 = aliased( ObjectInstance )
  desc1 = aliased( ObjectDescription )
  geo3 = aliased( GeometryModel )

  obj2 = aliased( ObjectInstance )
  desc2 = aliased( ObjectDescription )
  geo2 = aliased( GeometryModel )
  geo4 = aliased( GeometryModel )

  print "All Pots"
  for obj in any_obj_type(obj1, "Pot").all():
    print obj.name

  print "All Fuus"
  for obj in any_obj_type(obj2, "Fuu").all():
    print obj.name

  pairs = db().query( obj1, obj2, ST_3DDistance(geo1.geometry, geo2.geometry) ).filter( \
                                                                                                  obj1.id.in_( any_obj_type_ids(obj1, "Pot") ) , \
                                                                                                  obj2.id.in_( any_obj_type_ids(obj2, "Fuu") ),  \
                                                                                                  obj1.absolute_description_id == geo1.abstraction_desc, geo1.type == "Position3D", \
                                                                                                  obj2.absolute_description_id == geo2.abstraction_desc, geo2.type == "Position3D", \
                                                                                                  obj1.absolute_description_id == geo3.abstraction_desc, geo3.type == "FootprintBox", \
                                                                                                  obj2.absolute_description_id == geo4.abstraction_desc, geo4.type == "FootprintBox", \
                                                                                                  ST_3DDistance(geo1.geometry, geo2.geometry) < 1.0, \
                                                                                                  ST_Intersects(geo3.geometry, geo4.geometry) )


  print 'Pot / Foo / MinDist, / MaxDist'

  for p, f, dist in pairs.all():
    print p.name, f.name, dist

  pairs2 =  db().query( obj1, obj2, ST_3DDistance(geo1.geometry, geo2.geometry) ).filter(  \
                                                                                                  obj1.relative_description_id == desc1.id, desc1.type == "Pot", \
                                                                                                  obj2.relative_description_id == desc2.id, desc2.type == "Fuu", \
                                                                                                  obj1.absolute_description_id == geo1.abstraction_desc, geo1.type == "Position3D", \
                                                                                                  obj2.absolute_description_id == geo2.abstraction_desc, geo2.type == "Position3D", \
                                                                                                  obj1.absolute_description_id == geo3.abstraction_desc, geo3.type == "FootprintBox", \
                                                                                                  obj2.absolute_description_id == geo4.abstraction_desc, geo4.type == "FootprintBox", \
                                                                                                  ST_3DDistance(geo1.geometry, geo2.geometry) < 1.0, \
                                                                                                  ST_Intersects(geo3.geometry, geo4.geometry) )


  print 'Pot / Foo / MinDist, / MaxDist'

  for p, f, dist in pairs2.all():
    print p.name, f.name, dist

#  pairs3 = obj_geo( obj2.id, geo1, "Position3D" )

 # for p in pairs3:
  #  print p.type, p.id

  pairs4 = db().query( obj1, geo1, obj2, geo2, SFCGAL_Distance3D( geo1.geometry, geo2.geometry ) > 1.0).filter(

                                      obj1.id.in_( any_obj_type_ids( obj1, "Pot" ) ),
                                      geo1.id.in_( obj_geo( obj1.id, geo1, "Position3D" ) ),
                                      obj2.id.in_( any_obj_type_ids( obj2, "Fuu" ) ),
                                      geo2.id.in_( obj_geo( obj2.id, geo2, "Position3D" ) ),
                                      )
                                     #obj2.id.in_( any_obj_type_ids( obj2, "Fuu" ) ).label("second") , \
                                     #obj1.id == obj2.id  )#, \
                                     #geo2.id.in_( obj_geo_ids( obj2, geo2, "Position3D" ) ) )
                                     #obj_geo( obj1.id, geo2, "Position3D" ).label("secondg") ) #, \
                                     #SFCGAL_Distance3D( geo1.geometry, geo2.geometry ) > 3.5)


   ## , SFCGAL_Distance3D( obj_geo(obj1.id, geo1, "Position3D").label("obj_geo1"), obj_geo(obj2.id, geo1, "Position3D").label("obj_geo2") ) > 1.0)

  for o1, g1, o2, g2, d in pairs4.all():
    print 'Pot', o1.id, o1.name, g1.id, g1.type
    print 'Foo', o2.id, o2.name, g2.id, g2.type
    print 'Dist', d
 # res0 =  db().query( geo0.geometry ).filter( obj1.id == 2, geo0.type == "Body", obj1.absolute_description_id == geo0.object_description_id ).label( "res0" )
 # res1 =  db().query( geo1.geometry ).filter( obj2.id == 3, geo1.type == "Body", obj2.absolute_description_id == geo1.object_description_id ).label( "res1" )

  #root_dist = SFCGAL_Distance3D( origin, res0 ).label( "root_dist" )


  #print dists.all()
  #for d in dists.all():
  #  print d

  #print in_root_range.all()

  #obj_dist = SFCGAL_Distance3D( res0, res1 ).label( "obj_dist" )
  #in_obj_range = db().query( obj1.id, obj2.id, obj_dist ).filter( obj_dist > 0.0 )
  #print in_obj_range.all()

  #intersects = db().query( obj1.id, obj2.id, SFCGAL_Intersects3D( res0, res1 ) ).filter( obj1.id != obj2.id )
  #print intersects.all()
