plugins {
    kotlin("jvm") version "2.0.21"
}

group = "org.pramaan"
version = "1.0.0"

repositories { mavenCentral() }

dependencies { testImplementation(kotlin("test")) }

kotlin { jvmToolchain(17) }
tasks.test { useJUnitPlatform() }
