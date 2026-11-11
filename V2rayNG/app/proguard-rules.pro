# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# If your project uses WebView with JS, uncomment the following
# and specify the fully qualified class name to the JavaScript interface
# class:
#-keepclassmembers class fqcn.of.javascript.interface.for.webview {
#   public *;
#}

# Uncomment this to preserve the line number information for
# debugging stack traces.
#-keepattributes SourceFile,LineNumberTable

# If you keep the line number information, uncomment this to
# hide the original source file name.
#-renamesourcefileattribute SourceFile

# --- IranXray agent additions ------------------------------------------------
# Everything below exists because R8 is enabled per build with -PiranXrayMinify=true.

# The native tunnel is compiled with -DPKGNAME=com/v2ray/ang/service and reaches back into
# these classes through fixed JNI symbol names, which renaming would break.
-keep class com.v2ray.ang.service.** { *; }

# The Xray bridge is invoked from libgojni.so the same way.
-keep class libv2ray.** { *; }

# Profiles, settings and share-link payloads are (de)serialised by Gson using field names.
-keep class com.v2ray.ang.dto.** { *; }
-keep class com.v2ray.ang.dto.**$* { *; }
-keepclassmembers class com.v2ray.ang.dto.** { <fields>; }
-keepclassmembers enum com.v2ray.ang.** { *; }

# MMKV and its native peer look classes up by name.
-keep class com.tencent.mmkv.** { *; }

# Keep generic signatures and annotations: Gson reads them and drops the field type otherwise.
-keepattributes Signature, InnerClasses, EnclosingMethod
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations
-keepattributes AnnotationDefault

-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
