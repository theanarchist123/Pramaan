plugins {
    kotlin("jvm") version "2.0.21"
}

group = "org.pramaan"
version = "1.0.0"

repositories { mavenCentral() }

dependencies { testImplementation(kotlin("test")) }

// No toolchain pin: it builds with the JDK that runs Gradle (11 or newer; the SDK itself uses only JDK 11 APIs).
kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_11) } }
java { sourceCompatibility = JavaVersion.VERSION_11; targetCompatibility = JavaVersion.VERSION_11 }
tasks.test { useJUnitPlatform() }
