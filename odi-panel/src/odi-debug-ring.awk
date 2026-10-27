# Native OMCI RAW is one complete hex message per line. Keep line boundaries.
function rotate(file) {
 close(file)
 if(system("cp " file " " file ".1")!=0)return 0
 printf "%s", "" >file;close(file)
 return 1
}
BEGIN { bytes=0;wirebytes=0;seq=0; }
{
 size=length($0)+1
 # A protocol frame is much smaller than this. Keep draining on abnormal output.
 if(size>16384){print "oversized_record" >errorfile;close(errorfile);next}
 if(bytes+size>131072){if(!rotate(output)){print "rotation_failed" >errorfile;close(errorfile);next}bytes=0}
 print $0 >>output;fflush(output);bytes+=size
 if(wire!=""){
  record=(++seq) "|" $0
  if(wirebytes+length(record)+1>131072){if(!rotate(wire)){print "wire_rotation_failed" >errorfile;close(errorfile);next}wirebytes=0}
  print record >>wire;fflush(wire);wirebytes+=length(record)+1
 }
}
