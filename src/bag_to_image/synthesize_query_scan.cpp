#include <algorithm>
#include <cstdlib>
#include <ctime>
#include <fstream>
#include <iostream>
#include <math.h>
#include <random>
#include <vector>
#include "ros/ros.h"
#include "ros/package.h"
#include "rosbag/bag.h"
#include "rosbag/view.h"
#include "std_msgs/String.h"
#include "sensor_msgs/LaserScan.h"
#include "gui_msgs/ScanFeatureMsg.h"
#include "../perception_tools/perception_2d.h"
#include <CImg.h>
#include "shared_structs.h"

using std::string;
using std::vector;

//TODO: max laser range needs to be set in a single place and used with a single
//name. Currently, there are two ways of setting / using max range

unsigned int clip_l = 0;
unsigned int clip_u = 0;
//unsigned int clip_l = 28;
//unsigned int clip_u = 29;
float FOV = 270.0;
float min_range = 0.0;
float max_range = 10.0;
//string bag_name;
int synth_type_;

ros::Subscriber scan_feature_subscriber_;
ros::Publisher directory_publisher_;

float medianFilter(const vector<float> to_be_filtered) {
  if (to_be_filtered.size() % 2) {
    return to_be_filtered[to_be_filtered.size() / 2];
  }
  else {
    return (to_be_filtered[(to_be_filtered.size() / 2)] +
            to_be_filtered[(to_be_filtered.size() / 2) - 1]) / 2.0;
  }
}

bool epsilonClose(const float eps, const float n1, const float n2) {
  if (fabs(n1 - n2) <= eps) {
    return true;
  }
  return false;
}


vector<ScanFeatureMetaData> getFeaturesFromText(string filename) {
  std::string line;
  std::ifstream infile(filename);

  vector<ScanFeatureMetaData> all_features;

  while (std::getline(infile, line)) {
    std::istringstream iss(line);
    ScanFeatureMetaData scan_feature;

    //bag name, scan number, type, start angle, end angle, range[i], ..., range[j]

    string bag_name;
    iss >> bag_name;
    int scan_number;
    iss >> scan_number;
    int feature_type;
    iss >> feature_type;
    float start_angle;
    iss >> start_angle;
    float end_angle;
    iss >> end_angle;

    scan_feature.start_angle = start_angle;
    scan_feature.end_angle = end_angle;
    scan_feature.type = feature_type;

    float value;
    vector<float> ranges;
    while (iss >> value) {
      ranges.push_back(value);
    }

    scan_feature.ranges = ranges;

    std::cout << bag_name << " " << scan_number << " " << feature_type << " " 
              << start_angle << " " << end_angle << std::endl;
    // have scan feature, now generate many

    all_features.push_back(scan_feature);
  }
  return all_features;
}




  // Probably should be a feature that can be enabled by the type of query
  // (eg. anywhere in the scan vs. on the left side)
  //TODO: generate random location within the scan (optional, not doing right now)





//TODO: try: 
// tiling of feature
// can use setminus? ie the remaining part of the scan?

void generateFeatureOnlyScanFromFeatures(const vector<ScanFeatureMetaData> all_features, 
                                               vector<vector<float>>* all_scans) {

  //for // each feature // (only one feature at a time for now)
  int num_rays = all_features[0].ranges.size() *
      (FOV / ((all_features[0].end_angle - all_features[0].start_angle) * (180.0 / M_PI)));
  float angular_res = FOV / float(num_rays);
  float scan_start_angle = -FOV / 2.0;
  std::cout << "ranges size: " << all_features[0].ranges.size() << std::endl;
  std::cout << "angular res: " << angular_res << std::endl;
  std::cout << "scan start: " << scan_start_angle << std::endl;
  std::cout << "num rays: " << num_rays << std::endl;
  int feature_start_index = ((all_features[0].start_angle * (180.0/M_PI)) - scan_start_angle) / angular_res;
  int feature_end_index = feature_start_index + all_features[0].ranges.size();
  std::cout << "start: " << feature_start_index << std::endl;
  std::cout << "end: " << feature_end_index << std::endl;

  //TODO: set as command line input
  int scan_gen_type = 0;

  if (scan_gen_type == 0) {
    vector<float> single_scan;
    for (int k = 0; k < 11; ++k) {
      single_scan.clear();
      for (int i = 0; i < num_rays; ++i) { // each ray
        if (i >= feature_start_index && i <= feature_end_index) {
          single_scan.push_back(all_features[0].ranges[i - feature_start_index]);
        }
        else {
          // Set all depths to zero if not part of feature
          single_scan.push_back((float(k)/10.0) * max_range);
          //single_scan.push_back(0.0);
        }
      }
      all_scans->push_back(single_scan);
    }
   // all_scans->push_back(single_scan);
   // for (int k = 1; k < 11; ++k) {
     // single_scan.clear();
      //for (int i = 0; i < num_rays; ++i) { // each ray
          // Set all depths to zero
          //single_scan.push_back(0.0);
      //    single_scan.push_back((float(k)/10.0) * max_range);
     // }
      //all_scans->push_back(single_scan);
    //}
  }
  else if (scan_gen_type == 1) {
    vector<float> single_scan;
    for (int i = 0; i < num_rays; ++i) { // each ray
      if (i >= feature_start_index && i <= feature_end_index) {
        single_scan.push_back(all_features[0].ranges[i - feature_start_index]);
      }
      else {
        // Set all depths to max range if not part of feature
        single_scan.push_back(max_range);
      }
    }
    all_scans->push_back(single_scan);
    single_scan.clear();
    for (int i = 0; i < num_rays; ++i) { // each ray
        // Set all depths to max
        single_scan.push_back(max_range);
    }
    all_scans->push_back(single_scan);
  }
  else if (scan_gen_type == 2) {
    //TODO: this always tiles from start to end... should tiling be repeated for
    //every possible start point? (feature_size times)
    vector<float> single_scan;
    size_t feature_size = all_features[0].ranges.size();
    for (int i = 0; i < num_rays; ++i) { // each ray
      int feature_index = i % feature_size;
      single_scan.push_back(all_features[0].ranges[feature_index]);
    }
    all_scans->push_back(single_scan);
  }
}


//TODO: if more than one query scan is generated, can do statistics and generate
//a single query, OR aggregate queries and pick frequently occuring scans.




// random sample
//TODO: try:
// stepwise 0 to max

//   all of above but with variable feature depth
//   all of above but with variable feature angle
//   all of above but with both variable depth and variable angle

void generateMonteCarloScansFromFeatures(const vector<ScanFeatureMetaData> all_features, 
                                               vector<vector<float>>* all_scans) {
  //for // each feature // (only one feature at a time for now)
  int num_rays = (all_features[0].ranges.size() * FOV) / 
                 ((all_features[0].end_angle - all_features[0].start_angle) * (180.0 / M_PI));
  float angular_res = FOV / float(num_rays);
  float scan_start_angle = -FOV / 2.0;
  int feature_start_index = (scan_start_angle - all_features[0].start_angle) * angular_res;
  int feature_end_index = feature_start_index + all_features[0].ranges.size();
  int K = 1000;
  std::cout << "num rays: " << num_rays << std::endl;
  std::cout << "start: " << feature_start_index << std::endl;
  std::cout << "end: " << feature_end_index << std::endl;
  for (int k = 0; k < K; ++k) { // K times
   std::cout << k << std::endl;
   // Probably should be a feature that can be enabled by the type of query
    // (eg. anywhere in the scan vs. on the left side)
    //TODO: generate random location within the scan (optional, not doing right now)
    vector<float> single_scan;
    for (int i = 0; i < num_rays; ++i) { // each ray
      if (i >= feature_start_index && i <= feature_end_index) {
        single_scan.push_back(all_features[0].ranges[i - feature_start_index]);
      }
      else {
        // Sample depth from uniform distribution over laser range
        const float depth = static_cast <float> (rand()) / (static_cast <float> (RAND_MAX/max_range));
        single_scan.push_back(depth);
      }
    }
    all_scans->push_back(single_scan);
  }
}











void writeScans(vector<vector<float>>* all_scans) {
  std::ofstream outfile;
  //outfile.open("FeatureScans.txt", std::ios_base::app);
  //outfile.open("CorruptionQuality.txt", std::ios_base::app);
  //outfile.open("RawScans.txt", std::ios_base::app);
  for (size_t i = 0; i < all_scans->size(); ++i) {
    std::cout << "scan size: " << all_scans[0][i].size() << std::endl;
    for (size_t j = 0; j < all_scans[0][i].size(); ++j) {
      outfile << all_scans[0][i][j] << " ";
    }
    outfile << "\n";
  }
}

void convertScansToImagesPadAndFixedBounds(const vector<vector<float>>& all_scans) {
  string prefix;
  if (synth_type_ == 1) {
    prefix = "MCFeature";
  }
  else if (synth_type_ == 0) {
    prefix = "FeatureOnly";
  }

  std::cout << "size: " << all_scans.size() << std::endl;

  int num_obs = all_scans[0].size(); //how many points each scan has
  int padding = int((float(num_obs) / float(FOV)) * (360 - FOV));
  if (padding % 2) {
    padding--;
  }
  int length = num_obs + padding;
  int extra = length % 256;
  int deletion_interval = length / (extra + 1);

  //printf("Padding scans..."); fflush(stdout);
  vector<vector<float>> all_padded_scans;
  for (size_t i = 0; i < all_scans.size(); ++i) {
    vector<float> single_scan = all_scans[i];
    vector<float> padded_scan;
    for (int j = 0; j < (padding / 2); ++j) {
      padded_scan.push_back(0.0);
    }
    for (size_t j = 0; j < single_scan.size(); ++j) {
      padded_scan.push_back(single_scan[j]);
    }
    for (int j = 0; j < (padding / 2); ++j) {
      padded_scan.push_back(0.0);
    }
    // delete entries to make length k * 256 s.t. k is an int
    for (int j = extra; j > 0; j--) {
      padded_scan.erase(padded_scan.begin() + (j * deletion_interval));
    }
    all_padded_scans.push_back(padded_scan);
  }

  //printf("mod 256... should be 0: %d", int(all_padded_scans[0].size() % 256));
  //printf("size of scan: %d", int(all_padded_scans[0].size()));
  size_t downsampling_rate = all_padded_scans[0].size() / 256;
  //printf("downsample rate: %d", int(downsampling_rate));

  size_t width = 256;
  size_t height = 256;
  cimg_library::CImg<uint8_t> scan_image_rot(width, height);
  cimg_library::CImg<uint8_t> scan_image_norm(width, height);
  size_t scan_number = 1;

  std::ofstream outfile;
  //outfile.open("downsampledscans.txt", std::ios_base::app);
  //printf("Downsampling scans..."); fflush(stdout);

//  for (size_t i = 0; i < all_scans[0].size(); ++i) {
//    std::cout << all_scans[0][i];
//    if (((i + 1) % 5) == 0) {
//      std::cout << "\n";
//    }
//    else {
//      std::cout << ", ";
//    }
//  }
  //for (size_t i = 0; i < all_padded_scans[0].size(); ++i) {
  //  std::cout << all_padded_scans[0][i] << std::endl;
  //}

  for (size_t i = 0; i < all_padded_scans.size(); ++i) {
    vector<float> padded_scan = all_padded_scans[i];
    vector<float> downsampled_scan;
    for (size_t j = 0; j < padded_scan.size(); j += downsampling_rate) {
      vector<float> scan_seg;
      for (size_t k = j; k < j + downsampling_rate; ++k) {
        scan_seg.push_back(padded_scan[k]);
      }
      std::sort(scan_seg.begin(), scan_seg.end());
      float median = medianFilter(scan_seg);
      downsampled_scan.push_back(median);
    }

    for (size_t y = 0; y < height; ++y) {
      //outfile << size_t(255 - (downsampled_scan[y]/max_range)*255);
      for (size_t x = 0; x < downsampled_scan.size(); ++x) {
        scan_image_rot((x + y) % width, y) = size_t(255 - (downsampled_scan[x]/max_range)*255);
        scan_image_norm(x, y) = size_t(255 - (downsampled_scan[x]/max_range)*255);
      }
    }
    //outfile << "\n";
    string rot_scan_image_file = prefix + "_" + std::to_string(scan_number) + "_rot.png";
    string norm_scan_image_file = prefix + "_" + std::to_string(scan_number) + "_norm.png";
    scan_image_rot.save_png(rot_scan_image_file.c_str());
    scan_image_norm.save_png(norm_scan_image_file.c_str());
    scan_number++;
  }
  //printf(" Done.\n"); fflush(stdout);
}

void scanSelectionCallback(const gui_msgs::ScanFeatureMsg& msg) {

  //vector<ScanFeatureMetaData> all_features = getFeaturesFromText(msg.data);
  vector<ScanFeatureMetaData> all_features;

  ScanFeatureMetaData single_feature;
  single_feature.ranges = msg.ranges;
  single_feature.start_angle = msg.start_angle;
  single_feature.end_angle = msg.end_angle;
  single_feature.type = msg.type;

  float eps = 0.02;
  for (size_t i = 0; i < single_feature.ranges.size(); ++i) {
    if (epsilonClose(eps, single_feature.ranges[i], max_range)) {
      single_feature.ranges[i] = 0.0;
    }
  }


  all_features.push_back(single_feature);
  //std::cout << msg.data << std::endl;

  vector<vector<float>> all_scans;

  if (synth_type_ == 0) {
    generateFeatureOnlyScanFromFeatures(all_features, &all_scans);
  }
  else if (synth_type_ == 1) {
    //generateMonteCarloScansFromFeatures(all_features, &all_scans);
  }
  else {
    printf("Uknown synth type");
  }

  std::cout << "size: " << all_scans.size() << std::endl;
  //writeScans(&all_scans);
  convertScansToImagesPadAndFixedBounds(all_scans);

  std_msgs::String directory_message;
  if (synth_type_ == 0) {
    directory_message.data = "FO";
  }
  else if (synth_type_ == 1) {
    directory_message.data = "MC";
  }
  directory_publisher_.publish(directory_message);

}

int main(int argc, char* argv[]) {
  if (argc < 4) {
    printf("Usage: ./exec <synth_type (1=MonteCarlo or 0=FeatureOnly)> <FOV> <max_range>");
    fflush(stdout);
    exit(1);
  }
  synth_type_ = atoi(argv[1]);
  FOV = atof(argv[2]); // Field of View of the laser
  max_range = atof(argv[3]);

  ros::init(argc, argv, "synthesyzer");
  ros::NodeHandle nh;

  scan_feature_subscriber_ = nh.subscribe("ScanFeature", 1, scanSelectionCallback);
  directory_publisher_ = nh.advertise<std_msgs::String>("DataDirectory", 1, true);

  ros::spin();

  return 0;
}
