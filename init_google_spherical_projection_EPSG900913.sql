--
-- the EPSG params for PROJ4
-- target dbms: SQLite
--

--
-- setting up a transaction
--
BEGIN;

--
-- populating the "spatial_ref_sys" table
--
INSERT into spatial_ref_sys (srid, auth_name, auth_srid, ref_sys_name, proj4text) values (900913 ,'EPSG',900913,'Google Maps Global Mercator','+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs');


--
-- confirming the pending transaction
--
COMMIT;

--
-- all done * job completed *
--
