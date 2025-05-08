#define _GNU_SOURCE
#include <dlfcn.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

// Original function pointers
static void* (*real_dlopen)(const char* filename, int flags) = NULL;

// Configuration variables
#define MAX_MAPPINGS 1000
static char original_paths[MAX_MAPPINGS][1024] = {{0}};
static char target_paths[MAX_MAPPINGS][1024] = {{0}};
static int num_mappings = 0;
static int mappings_loaded = 0;

// Initialization function
static void init_real_functions() {
    if (!real_dlopen) {
        real_dlopen = dlsym(RTLD_NEXT, "dlopen");
    }
}

// Load path mappings from file
static void load_path_mappings() {
    if (mappings_loaded) return;
    
    const char* mapping_file = "/tmp/snaploader_path_mapping.txt";
    
    FILE* file = fopen(mapping_file, "r");
    if (!file) {
        return;
    }
    
    char line[2048];
    while (fgets(line, sizeof(line), file) && num_mappings < MAX_MAPPINGS) {
        // Remove newline
        size_t len = strlen(line);
        if (len > 0 && line[len-1] == '\n') {
            line[len-1] = '\0';
        }
        
        // Split by colon
        char* delimiter = strchr(line, ':');
        if (delimiter) {
            *delimiter = '\0';
            char* orig = line;
            char* target = delimiter + 1;
            
            strncpy(original_paths[num_mappings], orig, sizeof(original_paths[0]) - 1);
            original_paths[num_mappings][sizeof(original_paths[0]) - 1] = '\0';
            
            strncpy(target_paths[num_mappings], target, sizeof(target_paths[0]) - 1);
            target_paths[num_mappings][sizeof(target_paths[0]) - 1] = '\0';
            
            num_mappings++;
        }
    }
    
    fclose(file);
    mappings_loaded = 1;
}

// Redirect path
static const char* redirect_path(const char* path) {
    if (!path) return path;
    
    // Load mappings if not loaded yet
    if (!mappings_loaded) {
        load_path_mappings();
    }
    
    // Check for exact matches first
    for (int i = 0; i < num_mappings; i++) {
        if (strcmp(path, original_paths[i]) == 0) {
            return target_paths[i];
        }
    }
    
    // Check for partial matches (for libraries that might be loaded with relative paths)
    for (int i = 0; i < num_mappings; i++) {
        const char* basename_orig = strrchr(original_paths[i], '/');
        if (basename_orig) {
            basename_orig++; // Skip the '/'
            const char* basename_path = strrchr(path, '/');
            if (basename_path) {
                basename_path++; // Skip the '/'
                if (strcmp(basename_orig, basename_path) == 0) {
                    return target_paths[i];
                }
            }
        }
    }
    
    return path;
}

// Intercept dlopen
void* dlopen(const char* filename, int flags) {
    init_real_functions();
    
    const char* new_path = redirect_path(filename);
    
    void* result = real_dlopen(new_path, flags);
    
    if (!result && filename != new_path) {
        result = real_dlopen(filename, flags);
    }
    
    return result;
}
